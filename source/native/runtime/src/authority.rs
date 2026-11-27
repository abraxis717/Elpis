//! Successor session ownership and read-only compatibility status.
use elpis_ecs_c_session as ecs_c;
use elpis_ecs_c_session::model;

pub use ecs_c::register::{Cognition, Digest, Snapshot, StateFormat, ZERO};

use crate::code::{Code, Error, Rt};

/// What a runtime's sessions are created with (`elpis_runtime_config`): the entity capacity, the labels of the
/// founding operator and runtime, and an optional nonce seed. A zero seed draws a fresh nonce from the kernel for
/// every session; a nonzero seed derives each session's nonce from it and the session's ordinal, so two runtimes
/// configured alike open identical sessions (differential testing), while one runtime's successive sessions differ.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SessionTemplate {
    pub capacity: u32,
    pub nonce_seed: Digest,
    pub operator_label: Digest,
    pub runtime_label: Digest,
}

/// The domain of a derived session nonce.
const NONCE_DOMAIN: &[u8] = b"elpis.runtime.session-nonce.v1\x00";

impl SessionTemplate {
    /// `Invalid` for a capacity outside the session's bounds (checked at create, before any session exists).
    pub fn validate(&self) -> Result<(), Error> {
        if ecs_c::Session::volatile_bytes_for(self.capacity) == 0 {
            return Err(Rt::Invalid.into());
        }
        Ok(())
    }

    /// The session configuration of the `ordinal`-th session (from 1).
    fn config(&self, ordinal: u64) -> ecs_c::SessionConfig {
        let nonce = if self.nonce_seed == ZERO {
            ZERO // the session draws one (getrandom(2))
        } else {
            ecs_c::sha256::digest(&[NONCE_DOMAIN, &self.nonce_seed, &ordinal.to_le_bytes()])
        };
        ecs_c::SessionConfig {
            capacity: self.capacity,
            nonce,
            operator_label: self.operator_label,
            runtime_label: self.runtime_label,
        }
    }
}

/// The authority of one open runtime: its volatile ECS_C session.
pub struct Authority {
    session: ecs_c::Session,
    /// The last session refusal (RuntimeCore reports a mapped code; this is the exact one).
    last: Option<ecs_c::Code>,
}

/// What `elpis_runtime_authority_status` reports.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Status {
    /// Always [`BACKEND_ECS_C_SESSION`].
    pub backend: u32,
    /// The last session refusal (0: none).
    pub ecs_c_code: i32,
    pub entity_count: u32,
    pub capacity: u32,
    pub generation: u64,
    /// The session's process-unique instance (0: no session is open).
    pub instance: u64,
    pub receipt_count: u64,
    pub evidence_count: u64,
    /// The session's exact, constant memory footprint (0: no session is open).
    pub volatile_bytes: u64,
    /// Sessions this runtime has opened.
    pub sessions: u64,
    /// The next founding index and the reclaimed-row count (with the rows: what a relational view syncs from).
    pub next_founding_index: u64,
    pub reclaimed_count: u64,
    pub session: Digest,
    pub commit: Digest,
    pub state_root: Digest,
    pub receipt_head: Digest,
    /// The chain head of the evidence summaries the session recorded.
    pub evidence_head: Digest,
}

/// `elpis_runtime_authority.backend`: the volatile ECS_C session (ABI v8; v7's 2 was the durable ECS_C authority).
pub const BACKEND_ECS_C_SESSION: u32 = 3;

/// A session refusal in RuntimeCore's error domain.
pub fn map(code: ecs_c::Code) -> Error {
    use ecs_c::Code as E;
    let c = match code {
        E::Invalid => Code::Invalid,
        E::Unanchored => Code::Unanchored,
        E::AlreadyAnchored => Code::AlreadyAnchored,
        E::StateMismatch => Code::StateMismatch,
        E::EvolutionMismatch => Code::AuthorityMismatch,
        E::EvolutionPending => Code::EvolutionPending,
        E::EvolutionNotPending => Code::EvolutionNotPending,
        E::Exhausted => Code::Exhausted,
        E::Corrupt => Code::Corrupt,
        E::NoMem => return Error::Runtime(Rt::NoMem),
        E::PersistenceRetired => return Error::Runtime(Rt::Retired),
        _ => return Error::Runtime(Rt::Authority),
    };
    Error::Authority(c)
}

impl Authority {
    /// A fresh session: genesis (the founding operator and runtime, ACTIVE), nothing anchored. `NOMEM` when its
    /// memory cannot be reserved; `RUNTIME_AUTHORITY` when no nonce can be drawn. Nothing exists on refusal.
    pub fn create(template: &SessionTemplate, ordinal: u64) -> Result<Authority, (Error, ecs_c::Code)> {
        match ecs_c::Session::create(&template.config(ordinal)) {
            Ok(session) => Ok(Authority { session, last: None }),
            Err(code) => Err((map(code), code)),
        }
    }

    /// The view of the session: its generation, cognition lineage, format and evolution.
    pub fn snapshot(&self) -> Snapshot {
        let state = self.session.state();
        let (cognition, format) = match state.cognition {
            model::Cognition::Unanchored => (Cognition::Unanchored, StateFormat::K1),
            model::Cognition::Anchored { format, identity } => (Cognition::Anchored(identity), format),
        };
        Snapshot::with_format(self.session.generation(), cognition, format, state.evolution)
            .expect("the session's state satisfies the view's invariants")
    }

    /// An operator event on the open session: founding, lifecycle, source versions and reclamation. RuntimeCore's
    /// own kinds (anchor, publish, import, evolution) and genesis are `RUNTIME_INVALID`; the persistence-only kinds
    /// (legacy import, the three reconciliations) reach the session, which refuses them as retired
    /// (`RUNTIME_RETIRED`).
    pub fn operator_transition(&mut self, event: &model::Event) -> Result<ecs_c::SessionReceipt, Error> {
        use model::EventKind as K;
        if matches!(
            event.kind,
            K::Genesis | K::Anchor | K::Publish | K::ImportComposite | K::EvolutionReserve | K::EvolutionFinalize
        ) {
            return Err(Rt::Invalid.into());
        }
        let at = self.session.coordinate();
        self.session.transition(&at, event).map_err(|code| {
            self.last = Some(code);
            map(code)
        })
    }

    /// The entity row at `index` of the session (the operator's view for building an event). `RUNTIME_INVALID` past
    /// the last row.
    pub fn entity_at(&self, index: u32) -> Result<model::Entity, Error> {
        self.session.state().entities.get(index as usize).copied().ok_or_else(|| Rt::Invalid.into())
    }

    /// The identity the next ENTITY_FOUND of `kind` and `label` founds. `RUNTIME_INVALID` for an unknown kind.
    pub fn next_entity_id(&self, kind: u8, label: &Digest) -> Result<Digest, Error> {
        let kind = model::EntityKind::from_u8(kind).ok_or(Rt::Invalid)?;
        Ok(self.session.next_entity_id(kind, label))
    }

    /// The session's status (`sessions`: how many this runtime opened, this one included).
    pub fn status(&self, sessions: u64) -> Status {
        let s = &self.session;
        let state = s.state();
        Status {
            backend: BACKEND_ECS_C_SESSION,
            ecs_c_code: self.last.map(|c| c as i32).unwrap_or(0),
            entity_count: state.entities.len() as u32,
            capacity: s.capacity(),
            generation: s.generation(),
            instance: s.instance(),
            receipt_count: state.receipt_count,
            evidence_count: state.evidence_count,
            volatile_bytes: s.volatile_bytes() as u64,
            sessions,
            next_founding_index: state.next_founding_index,
            reclaimed_count: state.reclaimed_count,
            session: *s.lineage(),
            commit: *s.commit(),
            state_root: *s.state_root(),
            receipt_head: state.receipt_head,
            evidence_head: state.evidence_head,
        }
    }
}

// DEV-only scoped borrow; cannot create or mutate session authority.
#[cfg(feature="cognitive-native")]
impl Authority {
    pub(crate) fn cr5_borrow_session(&self) -> &ecs_c::Session { &self.session }
}
