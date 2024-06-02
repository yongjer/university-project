from gradio_client import Client


client = Client("http://127.0.0.1:7860")

res = client.predict("move forward for three seconds", "three\ntwo\none", api_name="/predict")
print(res)
# output the highest similarity index

# Find the maximum number in the list
max_number = max(res)

# Find the index of the maximum number
max_index = res.index(max_number)

print(f"The maximum number is {max_number} at index {max_index}")