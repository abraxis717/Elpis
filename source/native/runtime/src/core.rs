//! Standalone successor-only RuntimeCore. No legacy K1 capability or C ABI v8.
//! One fresh volatile session, one bounded native coordinator. Mutation remains
//! explicit and serialized through the native transaction and metering API.
use crate::authority::{Authority,Cognition,Digest,SessionTemplate,Snapshot,Status};
use crate::code::{Code,Error,Rt};

#[path="cognitive_native.rs"]
pub mod cognitive_native;

pub struct Core {
    template: SessionTemplate,
    sessions: u64,
    authority: Option<Authority>,
    refused: Option<i32>,
    cr5_prod: Option<cognitive_native::Persistent>,
}
impl Core {
    pub fn new(template:SessionTemplate)->Result<Self,Error>{
        template.validate()?;
        Ok(Self{template,sessions:0,authority:None,refused:None,cr5_prod:None})
    }
    pub fn open(&mut self)->Result<Snapshot,Error>{
        if self.authority.is_some(){return Err(Code::Open.into());}
        let ordinal=self.sessions.checked_add(1).ok_or(Code::Exhausted)?;
        let a=match Authority::create(&self.template,ordinal){
            Ok(a)=>a,
            Err((err,code))=>{self.refused=Some(code as i32);return Err(err);}
        };
        let snapshot=a.snapshot();
        self.sessions=ordinal;self.refused=None;self.authority=Some(a);
        Ok(snapshot)
    }
    // Native transaction/turn storage is destroyed before the borrowed session.
    pub fn close(&mut self){drop(self.cr5_prod.take());self.authority=None;}
    pub fn is_open(&self)->bool{self.authority.is_some()}
    fn live(&self)->Result<(),Error>{self.authority().map(|_|())}
    fn authority(&self)->Result<&Authority,Error>{self.authority.as_ref().ok_or(Rt::Closed.into())}
    fn authority_mut(&mut self)->Result<&mut Authority,Error>{self.authority.as_mut().ok_or(Rt::Closed.into())}
    pub fn snapshot(&self)->Result<Snapshot,Error>{Ok(self.authority()?.snapshot())}
    pub fn authority_status(&self)->Status{
        match &self.authority{
            Some(a)=>a.status(self.sessions),
            None=>Status{backend:crate::authority::BACKEND_ECS_C_SESSION,ecs_c_code:self.refused.unwrap_or(0),sessions:self.sessions,..Status::default()}
        }
    }
    // Same event filter and ECS_C law as CR6. No cached source-blind admission
    // table: the native enrollment authority reads the actual session on demand.
    pub fn authority_transition(&mut self,event:&elpis_ecs_c_session::model::Event)->Result<elpis_ecs_c_session::SessionReceipt,Error>{
        self.live()?;
        if self.cr5_prod.as_ref().is_some_and(|p|p.busy()){return Err(Rt::TurnOpen.into());}
        self.authority_mut()?.operator_transition(event)
    }
    pub fn authority_entity(&self,index:u32)->Result<elpis_ecs_c_session::model::Entity,Error>{self.authority()?.entity_at(index)}
    pub fn authority_next_entity_id(&self,kind:u8,label:&Digest)->Result<Digest,Error>{self.authority()?.next_entity_id(kind,label)}
}
impl Drop for Core{fn drop(&mut self){self.close();}}
