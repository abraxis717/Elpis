//! Standalone volatile cognitive runtime (DEV-only). The sealed legacy ABI v8
//! remains in the CR6 repository, not in this independently built projection.
#[cfg(not(feature="cognitive-native"))]
compile_error!("standalone successor requires cognitive-native");
mod authority;
pub mod code;
pub mod core;
pub use crate::core::Core;
pub use authority::{SessionTemplate,Status};
pub use code::{Error,Rt};
