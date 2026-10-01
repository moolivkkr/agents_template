// HARNESS STUBS — the app code testing/property-based.md's properties are written against: a Widget, a
// keyset paginator over a slice, and a reversible name encoding. They are what the properties test;
// the doc's subject is the property tests themselves.
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Widget {
    pub id: Uuid,
    pub name: String,
}

impl Widget {
    pub fn new(name: &str) -> Self {
        Self { id: Uuid::new_v4(), name: name.to_owned() }
    }
}

pub struct Page {
    pub items: Vec<Widget>,
    pub has_more: bool,
    pub cursor: Option<String>,
}

/// Keyset over the slice order: the cursor is the last returned item's id.
pub fn paginate(items: &[Widget], cursor: Option<&str>, page_size: usize) -> Page {
    let start = match cursor {
        Some(c) => items.iter().position(|w| w.id.to_string() == c).map_or(items.len(), |i| i + 1),
        None => 0,
    };
    let page: Vec<Widget> = items[start..].iter().take(page_size).cloned().collect();
    let has_more = start + page.len() < items.len();
    let cursor = if has_more { page.last().map(|w| w.id.to_string()) } else { None };
    Page { items: page, has_more, cursor }
}

pub fn encode(name: &str) -> String {
    URL_SAFE_NO_PAD.encode(name)
}

pub fn decode(encoded: &str) -> String {
    String::from_utf8(URL_SAFE_NO_PAD.decode(encoded).unwrap_or_default()).unwrap_or_default()
}
