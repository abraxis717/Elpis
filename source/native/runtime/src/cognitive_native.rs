//! Private DEV native cognitive API. Trusted serialized Rust owner only.
//! No model-facing ABI, paths, storage, callbacks from the caller or raw handles.
use super::*;
use elpis_ecs_c_session::{ffi as sf, Session};
use std::{cell::Cell, ffi::c_void, mem::MaybeUninit, ptr};

pub type NativeResult<T> = Result<T,i32>;
const INVALID:i32=300;
const BUSY:i32=301;
const TOKEN:i32=302;
const NOMEM:i32=36;
// Private DEV refusal codes, not public RuntimeCore ABI v8.
pub const RESIDENCY_LIMIT:i32=309;
pub const RESIDENCY_UNSUPPORTED:i32=310;
const RESIDENCY_INVARIANT:i32=305;
pub const RESIDENCY_MAX_BYTES:u64=64*1024*1024;
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub enum ResidencyTier { Hot, Warm, Cold }
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub enum ResidencyDomain { Ram, Device, Storage }
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub struct ResidencyPlan {pub component_bytes:u64,pub session_bytes:u64,pub context_bytes:u64,pub total_bytes:u64}
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub struct ResidencyInfo {pub plan:ResidencyPlan,pub ceiling_bytes:u64,pub tier:ResidencyTier,pub domain:ResidencyDomain,pub turn_hold:bool,pub transaction_open:bool}
// x86-64 layout of the exact CR5-P7B native archive, width 3. No allocation.
// Independent native layout and varied-capacity constructor parity are qualification gates.
// This is component payload, not allocator overhead, RSS, or a portable serialization.
pub fn residency_component_bytes(cells:u32,records:u32,links:u32)->NativeResult<u64>{
    if !cfg!(all(target_os="linux",target_arch="x86_64",target_pointer_width="64")){return Err(RESIDENCY_UNSUPPORTED);}
    if !(1..=1024).contains(&cells)||!(1..=1024).contains(&records)||!(1..=4096).contains(&links){return Err(INVALID);}
    Ok(19_609_534+16_253*u64::from(cells)+400*u64::from(records)+160*u64::from(links))
}
#[repr(C)]
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub struct Key { pub source:[u8;32], pub relation:[u8;32], pub scope:[u8;32] }
#[repr(C)]
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub struct Record {pub key:Key,pub source_version:u64,pub target:[u8;32],pub provenance:[u8;32],pub id:[u8;32]}
#[repr(C)]
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub struct Locator {pub state_owner:u64,pub state_epoch:u64,pub state_generation:u64,pub cell_owner:u64,pub cell_epoch:u64,pub cell_generation:u64,pub cell_revision:u64,pub vertex:u32,pub state_slot:u32,pub cell_slot:u32,pub cell_key:u32}
#[repr(C)]
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub struct Coordinate {pub session:[u8;32],pub instance:u64,pub generation:u64,pub state_root:[u8;32],pub store_instance:u64,pub revision:u64}
#[repr(C)]
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub struct Receipt {pub coordinate:Coordinate,pub transaction:u64}
#[repr(C)]
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub struct Answer {pub records:u32,pub locators:u32,pub distinct_conflict:u32,pub target:[u8;32]}
#[repr(C)]
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub struct Stats {pub physical:u32,pub adaptive:u32,pub records:u32,pub links:u32,pub open:u32,pub poisoned:u32,pub component_payload:usize}
#[repr(C)]
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub struct Limits {pub max_active:u32,pub max_rounds:u32,pub max_visits:u32}
#[repr(C)]
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub struct TransportStats {pub status:u32,pub rounds:u32,pub visits:u32,pub frontier_count:u32,pub enrolled:u32,pub arcs:u32,pub payload_bytes:usize}
#[repr(C)]
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub struct Budget(pub [u64;12]);
pub const CEILING:Budget=Budget([64,256,64,2048,512,4096,65536,393216,65536,256,6291456,262144]);
#[derive(Clone,Debug,PartialEq)]
pub struct CellImage {pub row:[f64;3],pub slow:[f64;120],pub fast:[f64;120],pub locator:Locator}
const _:()={assert!(std::mem::size_of::<Key>()==96);assert!(std::mem::size_of::<Record>()==200);assert!(std::mem::size_of::<Locator>()==72);assert!(std::mem::size_of::<Coordinate>()==96);assert!(std::mem::size_of::<Receipt>()==104);assert!(std::mem::size_of::<Answer>()==44);};
#[repr(C)]
struct Context {
    current:Cell<*const Session>,
    coordinate:unsafe extern "C" fn(*const Session,*mut sf::CCoordinate)->i32,
    at:unsafe extern "C" fn(*const Session,u32,*mut sf::CEntity)->i32,
    find:unsafe extern "C" fn(*const Session,*const [u8;32],*mut sf::CEntity)->i32,
    next:unsafe extern "C" fn(*const Session,u8,*const [u8;32],*mut [u8;32])->i32,
    check:unsafe extern "C" fn(*const Session,*const [u8;32],u64,*const [u8;32],*mut u32)->i32,
}
const _:()={assert!(std::mem::size_of::<Context>()==6*std::mem::size_of::<usize>());assert!(std::mem::size_of::<Stats>()==32);assert!(std::mem::size_of::<TransportStats>()==32);assert!(std::mem::size_of::<Limits>()==12);assert!(std::mem::size_of::<Budget>()==96);};
struct Clear<'a>(&'a Cell<*const Session>);
impl Drop for Clear<'_>{fn drop(&mut self){self.0.set(ptr::null());}}
impl Context {
    fn allocate()->NativeResult<Box<Self>>{unsafe{
        let p=std::alloc::alloc(std::alloc::Layout::new::<Self>()).cast::<Self>();
        if p.is_null(){return Err(NOMEM);}
        p.write(Self{current:Cell::new(ptr::null()),coordinate:sf::elpis_ecs_c_session_read_coordinate,at:sf::elpis_ecs_c_session_entity_at,find:sf::elpis_ecs_c_session_entity_find,next:sf::elpis_ecs_c_session_next_entity_id,check:sf::elpis_ecs_c_session_check_evidence});
        Ok(Box::from_raw(p))
    }}
    fn with<T>(&self,s:&Session,f:impl FnOnce()->NativeResult<T>)->NativeResult<T>{
        if !self.current.get().is_null(){return Err(BUSY);}
        self.current.set(s);let _clear=Clear(&self.current);f()
    }
}
#[link(name="cr5_production",kind="static")]
#[link(name="m")]
extern "C" {
    fn ct_create_borrowed(ctx:*mut c_void,cells:u32,records:u32,links:u32,width:u32,out:*mut *mut c_void)->i32;
    fn ct_destroy(r:*mut c_void);
    fn ct_coordinate(r:*const c_void,out:*mut Coordinate)->i32;
    fn ct_stats_read(r:*const c_void,out:*mut Stats)->i32;
    fn ct_vertex_code(r:*const c_void,v:u32,out:*mut u32)->i32;
    fn ct_budget_start(r:*mut c_void,b:*const Budget)->i32;
    fn ct_budget_end(r:*mut c_void)->i32;
    fn ct_budget_open(r:*const c_void)->i32;
    fn ct_budget_usage(r:*const c_void,b:*mut Budget)->i32;
    fn ct_begin(r:*mut c_void,c:*const Coordinate,out:*mut u64)->i32;
    fn ct_commit(r:*mut c_void,t:u64,out:*mut Receipt)->i32;
    fn ct_abort(r:*mut c_void,t:u64)->i32;
    fn ct_enroll(r:*mut c_void,t:u64,code:u32,row:*const f64,w:*const f64,record:*const Record)->i32;
    fn ct_attach(r:*mut c_void,t:u64,code:u32,record:*const Record)->i32;
    fn ct_adapt(r:*mut c_void,t:u64,code:u32,key:*const Key,id:*const u8,x:*const f64,y:*const f64)->i32;
    fn ct_propagate(r:*mut c_void,t:u64,codes:*const u32,n:u32,arcs:*const u32,m:u32,seeds:*const u32,ns:u32,limits:Limits,mode:u32,out:*mut TransportStats)->i32;
    fn ct_read(r:*const c_void,c:*const Coordinate,code:u32,row:*mut f64,width:u32,slow:*mut f64,fast:*mut f64,loc:*mut Locator)->i32;
    fn ct_lookup(r:*const c_void,c:*const Coordinate,key:*const Key,out:*mut Answer)->i32;
    fn ct_support_digest(x:*const f64,y:*const f64,out:*mut u8)->i32;
    fn eve_record_id(r:*const Record,out:*mut u8)->i32;
}
fn rc(code:i32)->NativeResult<()>{if code==0{Ok(())}else{Err(code)}}
fn output<T>(f:impl FnOnce(*mut T)->i32)->NativeResult<T>{let mut o=MaybeUninit::<T>::uninit();rc(f(o.as_mut_ptr()))?;Ok(unsafe{o.assume_init()})}
pub fn support_digest(x:&[f64;160],y:&[f64;96])->NativeResult<[u8;32]>{output(|o:*mut [u8;32]|unsafe{ct_support_digest(x.as_ptr(),y.as_ptr(),o.cast())})}
pub fn record_id(r:&Record)->NativeResult<[u8;32]>{output(|o:*mut [u8;32]|unsafe{eve_record_id(r,o.cast())})}
pub(super) struct Persistent {handle:*mut c_void,context:Box<Context>,token:Option<u64>,plan:ResidencyPlan,ceiling_bytes:u64}
// All operations require exclusive Core access; no session pointer survives a call.
unsafe impl Send for Persistent {}
impl Persistent {
    pub(super) fn busy(&self)->bool{self.token.is_some()||unsafe{ct_budget_open(self.handle)!=0}}
}
impl Drop for Persistent {fn drop(&mut self){unsafe{if let Some(t)=self.token.take(){let _=ct_abort(self.handle,t);}ct_destroy(self.handle);}}}
impl Core {
    pub fn cognitive_attach(&mut self,cells:u32,records:u32,links:u32)->NativeResult<()> {
        self.cognitive_attach_resident(cells,records,links,ResidencyTier::Warm,ResidencyDomain::Ram,RESIDENCY_MAX_BYTES)
    }
    pub fn cognitive_residency_plan(&self,cells:u32,records:u32,links:u32)->NativeResult<ResidencyPlan>{
        self.live().map_err(|e|e.code())?;
        let component_bytes=residency_component_bytes(cells,records,links)?;
        let session_bytes=self.authority_status().volatile_bytes;
        let context_bytes=std::mem::size_of::<Context>() as u64;
        let total_bytes=component_bytes.checked_add(session_bytes).and_then(|v|v.checked_add(context_bytes)).ok_or(RESIDENCY_LIMIT)?;
        Ok(ResidencyPlan{component_bytes,session_bytes,context_bytes,total_bytes})
    }
    pub fn cognitive_attach_resident(&mut self,cells:u32,records:u32,links:u32,tier:ResidencyTier,domain:ResidencyDomain,ceiling_bytes:u64)->NativeResult<()> {
        self.live().map_err(|e|e.code())?;
        if self.cr5_prod.is_some()||self.authority().map_err(|e|e.code())?.snapshot().cognition()!=Cognition::Unanchored{return Err(INVALID);}
        if tier!=ResidencyTier::Warm||domain!=ResidencyDomain::Ram{return Err(RESIDENCY_UNSUPPORTED);}
        let plan=self.cognitive_residency_plan(cells,records,links)?;
        if ceiling_bytes>RESIDENCY_MAX_BYTES||ceiling_bytes<plan.total_bytes{return Err(RESIDENCY_LIMIT);}
        let context=Context::allocate()?;
        let s=self.authority().map_err(|e|e.code())?.cr5_borrow_session();
        let mut handle=ptr::null_mut();
        context.with(s,||rc(unsafe{ct_create_borrowed((&*context as *const Context).cast_mut().cast(),cells,records,links,3,&mut handle)}))?;
        if handle.is_null(){return Err(INVALID);}
        let pending=Persistent{handle,context,token:None,plan,ceiling_bytes};
        // If a future native layout changes, do not publish an inaccurate charge.
        let actual:Stats=output(|o|unsafe{ct_stats_read(pending.handle,o)})?;
        if actual.component_payload as u64!=plan.component_bytes{return Err(RESIDENCY_INVARIANT);}
        self.cr5_prod=Some(pending);Ok(())
    }
    pub fn cognitive_residency(&self)->NativeResult<ResidencyInfo>{
        self.live().map_err(|e|e.code())?;
        let p=self.cr5_prod.as_ref().ok_or(INVALID)?;
        Ok(ResidencyInfo{plan:p.plan,ceiling_bytes:p.ceiling_bytes,tier:ResidencyTier::Warm,domain:ResidencyDomain::Ram,turn_hold:unsafe{ct_budget_open(p.handle)!=0},transaction_open:p.token.is_some()})
    }
    // Materialize is an explicit WARM-lane check: never creates an image, waits or promotes.
    pub fn cognitive_materialize(&self,tier:ResidencyTier,domain:ResidencyDomain)->NativeResult<ResidencyInfo>{
        if tier!=ResidencyTier::Warm||domain!=ResidencyDomain::Ram{return Err(RESIDENCY_UNSUPPORTED);}
        self.cognitive_residency()
    }
    // There is no lower mutable tier. A live session's learned state may not be evicted.
    pub fn cognitive_dematerialize(&self)->NativeResult<()>{
        let i=self.cognitive_residency()?;
        Err(if i.turn_hold||i.transaction_open{BUSY}else{RESIDENCY_UNSUPPORTED})
    }
    fn cognitive_call<T>(&mut self,f:impl FnOnce(*mut c_void,&mut Option<u64>)->NativeResult<T>)->NativeResult<T>{
        self.live().map_err(|e|e.code())?;
        let s=self.authority.as_ref().ok_or(Rt::Closed as i32)?.cr5_borrow_session();
        let p=self.cr5_prod.as_mut().ok_or(INVALID)?;
        let handle=p.handle;let token=&mut p.token;
        p.context.with(s,||f(handle,token))
    }
    pub fn cognitive_stats(&mut self)->NativeResult<Stats>{self.cognitive_call(|r,_|output(|o|unsafe{ct_stats_read(r,o)}))}
    pub fn cognitive_coordinate(&mut self)->NativeResult<Coordinate>{self.cognitive_call(|r,_|output(|o|unsafe{ct_coordinate(r,o)}))}
    pub fn cognitive_vertex(&mut self,v:u32)->NativeResult<u32>{self.cognitive_call(|r,_|output(|o|unsafe{ct_vertex_code(r,v,o)}))}
    pub fn cognitive_turn_start(&mut self,b:&Budget)->NativeResult<()>{self.cognitive_call(|r,_|rc(unsafe{ct_budget_start(r,b)}))}
    pub fn cognitive_turn_end(&mut self)->NativeResult<()>{self.cognitive_call(|r,_|rc(unsafe{ct_budget_end(r)}))}
    pub fn cognitive_usage(&mut self)->NativeResult<Budget>{self.cognitive_call(|r,_|output(|o|unsafe{ct_budget_usage(r,o)}))}
    pub fn cognitive_begin(&mut self)->NativeResult<()> {self.cognitive_call(|r,t|{if t.is_some(){return Err(BUSY);}let c=output(|o|unsafe{ct_coordinate(r,o)})?;*t=Some(output(|o|unsafe{ct_begin(r,&c,o)})?);Ok(())})}
    pub fn cognitive_enroll(&mut self,code:u32,row:&[f64;3],w:&[f64;120],e:&Record)->NativeResult<()>{self.cognitive_call(|r,t|rc(unsafe{ct_enroll(r,t.ok_or(TOKEN)?,code,row.as_ptr(),w.as_ptr(),e)}))}
    pub fn cognitive_associate(&mut self,code:u32,e:&Record)->NativeResult<()>{self.cognitive_call(|r,t|rc(unsafe{ct_attach(r,t.ok_or(TOKEN)?,code,e)}))}
    pub fn cognitive_adapt(&mut self,code:u32,k:&Key,id:&[u8;32],x:&[f64;160],y:&[f64;96])->NativeResult<()>{self.cognitive_call(|r,t|rc(unsafe{ct_adapt(r,t.ok_or(TOKEN)?,code,k,id.as_ptr(),x.as_ptr(),y.as_ptr())}))}
    pub fn cognitive_transport(&mut self,codes:&[u32],arcs:&[u32],seeds:&[u32],limits:Limits,mode:u32)->NativeResult<TransportStats>{
        self.cognitive_call(|r,t|{let token=t.ok_or(TOKEN)?;let n=u32::try_from(codes.len()).map_err(|_|INVALID)?;let m=u32::try_from(arcs.len()).map_err(|_|INVALID)?;let ns=u32::try_from(seeds.len()).map_err(|_|INVALID)?;
            output(|o|unsafe{ct_propagate(r,token,codes.as_ptr(),n,arcs.as_ptr(),m,seeds.as_ptr(),ns,limits,mode,o)})})
    }
    pub fn cognitive_commit(&mut self)->NativeResult<Receipt>{self.cognitive_call(|r,t|{let token=t.ok_or(TOKEN)?;let receipt=output(|o|unsafe{ct_commit(r,token,o)})?;*t=None;Ok(receipt)})}
    // Cleanup is intentionally available even after fail-stop, with no fuel or session reference required.
    pub fn cognitive_abort(&mut self)->NativeResult<()>{let p=self.cr5_prod.as_mut().ok_or(INVALID)?;let token=p.token.ok_or(TOKEN)?;rc(unsafe{ct_abort(p.handle,token)})?;p.token=None;Ok(())}
    pub fn cognitive_read(&mut self,code:u32)->NativeResult<CellImage>{self.cognitive_call(|r,_|{let c=output(|o|unsafe{ct_coordinate(r,o)})?;let mut row=[0.;3];let mut slow=[0.;120];let mut fast=[0.;120];let locator=output(|o|unsafe{ct_read(r,&c,code,row.as_mut_ptr(),3,slow.as_mut_ptr(),fast.as_mut_ptr(),o)})?;Ok(CellImage{row,slow,fast,locator})})}
    pub fn cognitive_lookup(&mut self,k:&Key)->NativeResult<Answer>{self.cognitive_call(|r,_|{let c=output(|o|unsafe{ct_coordinate(r,o)})?;output(|o|unsafe{ct_lookup(r,&c,k,o)})})}
}
