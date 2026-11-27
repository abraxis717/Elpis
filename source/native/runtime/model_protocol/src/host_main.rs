mod model_dispatch;
mod host_loop;
fn main(){host_loop::arm();if std::env::args_os().count()!=1{std::process::exit(125)}if host_loop::empty_core().and_then(host_loop::run).is_err(){std::process::exit(1)}}
