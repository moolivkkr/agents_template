// HARNESS STUB — grpc-pattern-rust.md imports `crate::grpc::convert::{to_proto, event_to_proto}`
// ("not shown"): the app's domain → proto mapping.
use crate::grpc::widget_server::proto;
use crate::services::{Widget, WidgetChange};

pub fn to_proto(w: &Widget) -> proto::Widget {
    proto::Widget { id: w.id.to_string(), name: w.name.clone(), description: w.description.clone(), ..Default::default() }
}

pub fn event_to_proto(e: &WidgetChange) -> proto::WidgetEvent {
    proto::WidgetEvent { widget: Some(to_proto(&e.widget)), ..Default::default() }
}
