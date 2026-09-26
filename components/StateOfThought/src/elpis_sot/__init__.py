"""Branch43 State-of-Thought (SoT) R0. Inactive component: no runtime admission,
no registry wiring, no ECS/RRSI path. See elpis_sot.core."""
from .core import (
    SOT_CORE12_R0,
    SOT_DYN4_R0,
    FastGuardReason,
    InferenceEpochBinding,
    SoTContractError,
    SoTFastControlState,
    SoTFastSteeringApplication,
    SoTFastSteeringProposal,
    SoTObserverState,
    SteeringOutcome,
    apply_fast_steering,
    bind_completed_epoch,
    frozen_steering_contract,
    frozen_steering_contract_digest,
    global_event_fields,
    initial_fast_control_state,
    observe_epoch,
    propose_fast_steering,
    width_transport_digest,
    width_transport_matrix,
)

__all__ = (
    'SOT_CORE12_R0', 'SOT_DYN4_R0', 'FastGuardReason', 'InferenceEpochBinding', 'SoTContractError',
    'SoTFastControlState', 'SoTFastSteeringApplication', 'SoTFastSteeringProposal', 'SoTObserverState',
    'SteeringOutcome', 'apply_fast_steering', 'bind_completed_epoch',
    'frozen_steering_contract', 'frozen_steering_contract_digest', 'global_event_fields',
    'initial_fast_control_state', 'observe_epoch', 'propose_fast_steering', 'width_transport_digest', 'width_transport_matrix',
)
