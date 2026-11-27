//! Bounded serialized host: trusted supervisor supplies distinct model/operator pipe capabilities.
use crate::model_dispatch::{Dispatcher,Decision,Owner,Ticket};
use elpis_runtime::{Core,SessionTemplate};
use elpis_runtime::core::cognitive_native as c;
const MAX:usize=2308;
const TICKS:u32=65536;
const OP_LIMIT:u64=4096;
#[repr(C)]
struct Lane {rx:[u8;2312],tx:[u8;2312],used:u32,target:u32,queued:u32,role:i32,closed:i32}
const _:()={assert!(std::mem::size_of::<Lane>()==4644);assert!(std::mem::offset_of!(Lane,closed)==4640);};
#[link(name="cr6_ipc",kind="static")]
extern "C" {fn cr6_ipc_init(l:*mut Lane,role:i32)->i32;fn cr6_ipc_close(l:*mut Lane);fn cr6_ipc_poll(m:*mut Lane,o:*mut Lane,ms:i32)->i32;fn cr6_ipc_receive(l:*mut Lane)->i32;fn cr6_ipc_peek(l:*const Lane,p:*mut *const u8,n:*mut usize)->i32;fn cr6_ipc_consume(l:*mut Lane)->i32;fn cr6_ipc_queue(l:*mut Lane,p:*const u8,n:usize)->i32;fn cr6_ipc_flush(l:*mut Lane)->i32;}
#[link(name="cr6_ipc_guard",kind="static")]
extern "C"{fn cr6_ipc_guard();}
pub fn arm(){unsafe{cr6_ipc_guard()}}
impl Lane {
 fn new(role:i32)->Self{let mut l=Self{rx:[0;2312],tx:[0;2312],used:0,target:0,queued:0,role,closed:0};assert_eq!(unsafe{cr6_ipc_init(&mut l,role)},0);l}
 fn closed(&self)->bool{self.closed!=0}
 fn close(&mut self){unsafe{cr6_ipc_close(self)}}
 fn flush(&mut self){if !self.closed(){unsafe{cr6_ipc_flush(self)};}}
 fn receive(&mut self,b:&mut [u8;MAX])->Result<Option<usize>,()>{if self.closed()||self.queued!=0{return Ok(None)};let rc=unsafe{cr6_ipc_receive(self)};if rc==-1{return Ok(None)}if rc<0{return Err(())}if rc!=2{return Ok(None)}let mut p=std::ptr::null();let mut n=0; if unsafe{cr6_ipc_peek(self,&mut p,&mut n)}!=2||p.is_null()||n==0||n>MAX{return Err(())}b[..n].copy_from_slice(unsafe{std::slice::from_raw_parts(p,n)});if unsafe{cr6_ipc_consume(self)}!=1{return Err(())}Ok(Some(n))}
 fn queue(&mut self,b:&[u8])->Result<(),()>{if unsafe{cr6_ipc_queue(self,b.as_ptr(),b.len())}!=1{return Err(())}Ok(())}
}
impl Drop for Lane{fn drop(&mut self){self.close()}}
struct Pending{ticket:Ticket,id:u64,wire:[u8;MAX],reviewed:bool}
fn u16at(b:&[u8],i:usize)->u16{u16::from_le_bytes(b[i..i+2].try_into().unwrap())}
fn u64at(b:&[u8],i:usize)->u64{u64::from_le_bytes(b[i..i+8].try_into().unwrap())}
fn status(b:&[u8])->u32{u32::from_le_bytes(b[12..16].try_into().unwrap())}
fn put(b:&mut [u8],i:usize,v:&[u8]){b[i..i+v.len()].copy_from_slice(v)}
fn put_coord(b:&mut [u8],v:&c::Coordinate){put(b,0,&v.session);put(b,32,&v.instance.to_le_bytes());put(b,40,&v.generation.to_le_bytes());put(b,48,&v.state_root);put(b,80,&v.store_instance.to_le_bytes());put(b,88,&v.revision.to_le_bytes());}
fn reply(op:u16,seq:u64,id:u64,status:u32,detail:u32,coord:Option<c::Coordinate>)->[u8;128]{let mut b=[0;128];put(&mut b,0,b"EOR1");put(&mut b,4,&1u16.to_le_bytes());put(&mut b,6,&op.to_le_bytes());put(&mut b,8,&status.to_le_bytes());put(&mut b,12,&detail.to_le_bytes());put(&mut b,16,&seq.to_le_bytes());put(&mut b,24,&id.to_le_bytes());if let Some(v)=coord{put_coord(&mut b[32..],&v)}b}
fn observe(m:&Lane,o:&Lane,d:&mut Dispatcher,owner:&mut Option<Owner>,p:&mut Option<Pending>)->Result<(),()>{if m.closed(){if let Some(v)=owner.take(){d.disconnect(v).map_err(|_|())?;}*p=None;}if o.closed(){if let Some(v)=p.take(){let _=d.decide(v.ticket,false);}if d.pending().is_some(){return Err(())}}Ok(())}
fn poll(m:&mut Lane,o:&mut Lane,ms:i32)->Result<(),()>{let r=unsafe{cr6_ipc_poll(m,o,ms)};if r<0&&!(m.closed()&&o.closed()){Err(())}else{Ok(())}}
pub fn empty_core()->Result<Core,()>{let mut core=Core::new(SessionTemplate{capacity:16,nonce_seed:[0;32],operator_label:[1;32],runtime_label:[2;32]}).map_err(|_|())?;core.open().map_err(|_|())?;core.cognitive_attach(1024,1024,4096).map_err(|_|())?;Ok(core)}
/// Operator commands are fixed 24 bytes: ELO1, LE16 version, LE16 op, LE64 sequence, LE64 proposal ID.
/// 1 STATUS(id=0), 2 REVIEW, 3 APPROVE, 4 REJECT. REVIEW returns the exact 2308-byte ELQ1 proposal.
/// Other replies are EOR1 128 bytes; status 0 OK, 1 committed, 2 rejected, 3 native refusal, 4 missing/unreviewed, 5 committed-cleanup-fault, 6 unavailable.
/// Only trusted operator capability can review/decide. No model reconnect in this host instance.
pub fn run(core:Core)->Result<(),()>{
 let mut d=Dispatcher::new(core).map_err(|_|())?;let (own,next)=d.connect().map_err(|_|())?;if next!=1{return Err(())}let mut owner=Some(own);let mut m=Lane::new(0);let mut o=Lane::new(1);let mut pending:Option<Pending>=None;let mut seq=1u64;let mut b=[0;MAX];let mut ended=false;let mut fault=false;
 for _ in 0..TICKS{
  poll(&mut m,&mut o,100)?;observe(&m,&o,&mut d,&mut owner,&mut pending)?;if m.closed()&&o.closed(){ended=true;break}
  m.flush();o.flush();observe(&m,&o,&mut d,&mut owner,&mut pending)?;
  if !fault {if let Some(n)=m.receive(&mut b)?{if let Some(v)=owner{match d.dispatch(v,&b[..n]){
   Ok(r)=>{let r=r.wire();if status(r)==1 {let ticket=d.pending().ok_or(())?.ticket;if o.closed(){let _=d.decide(ticket,false);if d.pending().is_some(){return Err(())}let mut unavailable=[0;32];unavailable.copy_from_slice(r);put(&mut unavailable,12,&7u32.to_le_bytes());m.queue(&unavailable)?;}else{if n!=MAX||pending.is_some(){return Err(())}pending=Some(Pending{ticket,id:u64at(r,16),wire:b,reviewed:false});m.queue(r)?;}}else{if d.pending().is_none(){pending=None;}m.queue(r)?;}},
   Err(_)=>m.close(),
  }}}}observe(&m,&o,&mut d,&mut owner,&mut pending)?;
  if let Some(n)=o.receive(&mut b)?{
   if n!=24||&b[..4]!=b"ELO1"||u16at(&b,4)!=1||u64at(&b,8)!=seq||seq>OP_LIMIT{ o.close();observe(&m,&o,&mut d,&mut owner,&mut pending)?;continue; }
   let op=u16at(&b,6);let id=u64at(&b,16);if !(1..=4).contains(&op)||(op==1)!=(id==0){o.close();observe(&m,&o,&mut d,&mut owner,&mut pending)?;continue}let s=seq;seq+=1;
   // Observe both peers once more before the trusted decision. A commit already in flight is not revoked by later peer death.
   poll(&mut m,&mut o,0)?;observe(&m,&o,&mut d,&mut owner,&mut pending)?;if o.closed(){continue}
   if fault {o.queue(&reply(op,s,id,6,0,None))?;continue}
   if op==1{let co=d.operator_coordinate().ok();o.queue(&reply(op,s,pending.as_ref().map_or(0,|p|p.id),if co.is_some(){0}else{6},0,co))?;}
   else if op==2{match pending.as_mut(){Some(p) if p.id==id=>{o.queue(&p.wire)?;p.reviewed=true;},_=>o.queue(&reply(op,s,id,4,0,None))?}}
   else if pending.as_ref().is_some_and(|p|p.id==id&&(op==4||p.reviewed)){
    let p=pending.take().unwrap();let (st,detail,co)=match d.decide(p.ticket,op==3){Decision::Rejected=>(2,0,d.operator_coordinate().ok()),Decision::Refused(e)=>(3,e,d.operator_coordinate().ok()),Decision::Committed{receipt,cleanup_ok}=>{fault=!cleanup_ok;(if cleanup_ok{1}else{5},0,Some(receipt.coordinate))}};o.queue(&reply(op,s,id,st,detail,co))?;if fault{m.close();observe(&m,&o,&mut d,&mut owner,&mut pending)?;}
   }else{o.queue(&reply(op,s,id,4,0,None))?;}
  }
  m.flush();o.flush();observe(&m,&o,&mut d,&mut owner,&mut pending)?;
 }
 m.close();o.close();observe(&m,&o,&mut d,&mut owner,&mut pending)?;d.close();if ended&&!fault{println!("HOST_LOOP_CLOSE=PASS");Ok(())}else{Err(())}
}
