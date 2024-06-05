from gradio_client import Client, file

client = Client("http://localhost:7863/")
result = client.view_api(
)
print(result)