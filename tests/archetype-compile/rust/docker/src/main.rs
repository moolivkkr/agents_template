#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    yourapp::serve("yourapp").await
}
