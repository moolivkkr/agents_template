#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    yourapp::serve("order-service").await
}
