//! DEV transport-neutral dispatcher. Trusted caller owns connection/decision authority.
//! No I/O, threads, persistent state, model authentication or public RuntimeCore ABI change.
use elpis_runtime::Core;
use elpis_runtime::core::cognitive_native as c;
use elpis_ecs_c_session::model::Event;
const MAX_FRAME:usize=2308;
const MAX_ATTEMPTS:u64=4096;
const MAX_CONNECTIONS:u64=64;
const OK:u32=0; const PROPOSED:u32=1; const INVALID:u32=2; const STALE:u32=3;
const REFUSED:u32=4; const BUSY:u32=5; const LIMIT:u32=6; const UNAVAILABLE:u32=7;
#[repr(C)]
struct Message { request_id:u64,length:u32,status:u32,op:u16,payload:[u8;2276] }
const _:()={assert!(std::mem::size_of::<Message>()==2296);assert!(std::mem::offset_of!(Message,request_id)==0);assert!(std::mem::offset_of!(Message,length)==8);assert!(std::mem::offset_of!(Message,status)==12);assert!(std::mem::offset_of!(Message,op)==16);assert!(std::mem::offset_of!(Message,payload)==18);};
#[link(name="cr6_protocol",kind="static")]
extern "C" {
    fn emp_decode(response:u32,wire:*const u8,size:usize,out:*mut Message)->i32;
    fn emp_encode(response:u32,msg:*const Message,wire:*mut u8,capacity:usize,written:*mut usize)->i32;
}
impl Message {fn empty()->Self{Self{request_id:0,length:0,status:0,op:0,payload:[0;2276]}}}
#[derive(Clone,Copy,Debug,PartialEq,Eq)] pub struct Owner {epoch:u64,session:[u8;32],instance:u64,store:u64}
#[derive(Clone,Copy,Debug,PartialEq,Eq)] pub struct Ticket {owner:Owner,id:u64}
#[derive(Clone,Debug,PartialEq)] pub struct Proposal { pub ticket:Ticket,pub coordinate:c::Coordinate,pub vertex:u32,pub key:c::Key,pub record_id:[u8;32],pub x:[f64;160],pub y:[f64;96] }
#[derive(Clone,Copy,Debug,PartialEq,Eq)] pub enum Failure {Owner,Sequence,Limit,Codec(i32),Unavailable}
#[derive(Clone,Copy,Debug,PartialEq,Eq)] pub enum Decision {Rejected,Refused(u32),Committed{receipt:c::Receipt,cleanup_ok:bool}}
pub struct Reply {bytes:[u8;MAX_FRAME],len:usize}
impl Reply {pub fn wire(&self)->&[u8]{&self.bytes[..self.len]}}
fn arr<const N:usize>(s:&[u8],off:usize)->[u8;N]{s[off..off+N].try_into().unwrap()}
fn u32at(s:&[u8],off:usize)->u32{u32::from_le_bytes(arr(s,off))}
fn u64at(s:&[u8],off:usize)->u64{u64::from_le_bytes(arr(s,off))}
fn coordinate(s:&[u8])->c::Coordinate{c::Coordinate{session:arr(s,0),instance:u64at(s,32),generation:u64at(s,40),state_root:arr(s,48),store_instance:u64at(s,80),revision:u64at(s,88)}}
fn put(s:&mut [u8],off:usize,v:&[u8]){s[off..off+v.len()].copy_from_slice(v);}
fn put_coord(s:&mut [u8],v:&c::Coordinate){put(s,0,&v.session);put(s,32,&v.instance.to_le_bytes());put(s,40,&v.generation.to_le_bytes());put(s,48,&v.state_root);put(s,80,&v.store_instance.to_le_bytes());put(s,88,&v.revision.to_le_bytes());}
fn key(s:&[u8],off:usize)->c::Key{c::Key{source:arr(s,off),relation:arr(s,off+32),scope:arr(s,off+64)}}
fn status(e:i32)->u32{match e{304=>STALE,301=>BUSY,308|309|36=>LIMIT,305=>UNAVAILABLE,_=>REFUSED}}
pub struct Dispatcher {core:Core,owner:Option<Owner>,epochs:u64,next:u64,attempts:u64,pending:Option<Proposal>,fault:bool}
impl Dispatcher {
    pub fn new(mut core:Core)->Result<Self,Failure>{let r=core.cognitive_residency().map_err(|_|Failure::Unavailable)?;if r.turn_hold||r.transaction_open||core.cognitive_coordinate().is_err(){return Err(Failure::Unavailable)}Ok(Self{core,owner:None,epochs:0,next:1,attempts:0,pending:None,fault:false})}
    pub fn connect(&mut self)->Result<(Owner,u64),Failure>{if self.fault{return Err(Failure::Unavailable)}if self.owner.is_some(){return Err(Failure::Owner)}if self.epochs>=MAX_CONNECTIONS||self.attempts>=MAX_ATTEMPTS{return Err(Failure::Limit)}let c=self.core.cognitive_coordinate().map_err(|_|Failure::Unavailable)?;self.epochs+=1;let o=Owner{epoch:self.epochs,session:c.session,instance:c.instance,store:c.store_instance};self.owner=Some(o);Ok((o,self.next))}
    pub fn disconnect(&mut self,o:Owner)->Result<(),Failure>{if self.owner!=Some(o){return Err(Failure::Owner)}self.pending=None;self.owner=None;Ok(())}
    pub fn pending(&self)->Option<&Proposal>{self.pending.as_ref()}
    fn fault(&mut self){self.fault=true;self.pending=None;}
    fn read<T>(&mut self,f:impl FnOnce(&mut Core)->c::NativeResult<T>)->Result<T,u32>{
        if self.fault{return Err(UNAVAILABLE)}
        if let Err(e)=self.core.cognitive_turn_start(&c::Budget([0,0,0,0,0,1,0,0,0,0,0,0])){self.fault();return Err(status(e))}
        let v=f(&mut self.core);if self.core.cognitive_turn_end().is_err(){self.fault();return Err(UNAVAILABLE)}v.map_err(status)
    }
    // These are trusted host methods, not wire operations.
    pub fn operator_transition(&mut self,e:&Event)->bool{!self.fault&&self.core.authority_transition(e).is_ok()}
    pub fn operator_cell(&mut self,vertex:u32)->Result<c::CellImage,u32>{self.read(|r|{let v=r.cognitive_vertex(vertex)?;r.cognitive_read(v)})}
    pub fn operator_coordinate(&mut self)->c::NativeResult<c::Coordinate>{self.core.cognitive_coordinate()}
    pub fn operator_core(&self)->&Core{&self.core}
    pub fn dispatch(&mut self,o:Owner,wire:&[u8])->Result<Reply,Failure>{
        if self.fault{return Err(Failure::Unavailable)}if self.owner!=Some(o){return Err(Failure::Owner)}
        if self.attempts>=MAX_ATTEMPTS{return Err(Failure::Limit)}self.attempts+=1;
        let mut req=Message::empty();let rc=unsafe{emp_decode(0,wire.as_ptr(),wire.len(),&mut req)};if rc!=0{return Err(Failure::Codec(rc))}
        if req.request_id!=self.next{return Err(Failure::Sequence)}self.next+=1;
        let mut res=Message::empty();res.request_id=req.request_id;res.op=req.op;
        res.status=self.execute(o,&req,&mut res);if res.status!=OK{res.length=0;}
        let mut out=Reply{bytes:[0;MAX_FRAME],len:0};let rc=unsafe{emp_encode(1,&res,out.bytes.as_mut_ptr(),out.bytes.len(),&mut out.len)};if rc!=0{self.fault();return Err(Failure::Codec(rc))}Ok(out)
    }
    fn execute(&mut self,o:Owner,r:&Message,out:&mut Message)->u32{
        let current=match self.core.cognitive_coordinate(){Ok(v)=>v,Err(e)=>return status(e)};
        if r.op!=1&&coordinate(&r.payload)!=current{return STALE}
        let b=&mut out.payload;
        match r.op {
            1=>{let s=match self.core.cognitive_stats(){Ok(v)=>v,Err(e)=>return status(e)};put_coord(b,&current);for (i,v) in [s.physical,s.adaptive,s.records,s.links].into_iter().enumerate(){put(b,96+i*4,&v.to_le_bytes());}put(b,112,&(s.component_payload as u64).to_le_bytes());out.length=128;OK},
            2=>{let k=key(&r.payload,96);let a=match self.read(|c|c.cognitive_lookup(&k)){Ok(v)=>v,Err(e)=>return e};put_coord(b,&current);for(i,v)in [a.records,a.locators,a.distinct_conflict].into_iter().enumerate(){put(b,96+4*i,&v.to_le_bytes());}put(b,108,&a.target);out.length=140;OK},
            3=>{let v=u32at(&r.payload,96);let a=match self.operator_cell(v){Ok(v)=>v,Err(e)=>return e};put_coord(b,&current);for(i,v)in a.row.into_iter().enumerate(){put(b,96+8*i,&v.to_le_bytes());}put(b,120,&a.locator.cell_revision.to_le_bytes());out.length=128;OK},
            4=>{if self.pending.is_some(){return BUSY}let vertex=u32at(&r.payload,96);if self.core.cognitive_vertex(vertex).is_err(){return INVALID}let mut x=[0.;160];let mut y=[0.;96];for(i,v)in x.iter_mut().enumerate(){*v=f64::from_bits(u64at(&r.payload,228+8*i));}for(i,v)in y.iter_mut().enumerate(){*v=f64::from_bits(u64at(&r.payload,1508+8*i));}self.pending=Some(Proposal{ticket:Ticket{owner:o,id:r.request_id},coordinate:current,vertex,key:key(&r.payload,100),record_id:arr(&r.payload,196),x,y});PROPOSED},
            _=>INVALID
        }
    }
    pub fn decide(&mut self,ticket:Ticket,approve:bool)->Decision{
        if self.fault{return Decision::Refused(UNAVAILABLE)}
        if self.owner!=Some(ticket.owner)||self.pending.as_ref().map(|p|p.ticket)!=Some(ticket){return Decision::Refused(REFUSED)}
        let p=self.pending.take().unwrap(); // Consume once, even on stale, rejection or failed execution.
        if !approve{return Decision::Rejected}
        match self.core.cognitive_coordinate(){Ok(v) if v==p.coordinate=>{},Ok(_)=>return Decision::Refused(STALE),Err(e)=>return Decision::Refused(status(e))}
        let code=match self.core.cognitive_vertex(p.vertex){Ok(v)=>v,Err(e)=>return Decision::Refused(status(e))};
        // One exact native R97W episode; no caller-provided fuel or native token.
        let budget=c::Budget([1,0,1,32,8,0,0,0,0,0,0,0]);
        if let Err(e)=self.core.cognitive_turn_start(&budget){self.fault();return Decision::Refused(status(e))}
        if let Err(e)=self.core.cognitive_begin(){if self.core.cognitive_turn_end().is_err(){self.fault();}return Decision::Refused(status(e))}
        let result=self.core.cognitive_adapt(code,&p.key,&p.record_id,&p.x,&p.y).and_then(|_|self.core.cognitive_commit());
        match result{
            Ok(receipt)=>{let cleanup_ok=self.core.cognitive_turn_end().is_ok();if !cleanup_ok{self.fault();}Decision::Committed{receipt,cleanup_ok}},
            Err(e)=>{if self.core.cognitive_abort().is_err()||self.core.cognitive_turn_end().is_err(){self.fault();return Decision::Refused(UNAVAILABLE)}Decision::Refused(status(e))}
        }
    }
    pub fn close(mut self){self.pending=None;self.owner=None;self.core.close();}
}
