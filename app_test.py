import os
import json
import gradio as gr
from PIL import Image
import urllib.request
import urllib.parse
import uuid
import websocket
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)

class ComfyUIClient:
    def __init__(self, server_address, port, user_id=None):
        self.server_address = f"{server_address}:{port}"
        self.user_id = user_id if user_id else str(uuid.uuid4())
        self.ws = None

    def connect(self):
        self.ws = websocket.WebSocket()
        self.ws.connect(f"ws://{self.server_address}/ws?clientId={self.user_id}")

    def close_connection(self):
        if self.ws:
            self.ws.close()
            self.ws = None

    def queue_prompt(self, prompt):
        p = {"prompt": prompt, "client_id": self.user_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request(f"http://{self.server_address}/prompt", data=data)
        return json.loads(urllib.request.urlopen(req).read())

    def get_image(self, filename, subfolder, folder_type):
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(data)
        with urllib.request.urlopen(f"http://{self.server_address}/view?{url_values}") as response:
            return response.read()

    def get_history(self, prompt_id):
        with urllib.request.urlopen(f"http://{self.server_address}/history/{prompt_id}") as response:
            return json.loads(response.read())

    def get_images(self, prompt):
        prompt_id = self.queue_prompt(prompt)['prompt_id']
        output_images = {}
        try:
            while True:
                out = self.ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    print("STR Received from ComfyUI server:", message)
                    if message['type'] == 'executing':
                        data = message['data']
                        if data['node'] is None and data['prompt_id'] == prompt_id:
                            break  # Execution is done
                else:
                    continue  # previews are binary data

            history = self.get_history(prompt_id)[prompt_id]
            print("OBJ Received from ComfyUI server:", history)
            for o in history['outputs']:
                for node_id in history['outputs']:
                    node_output = history['outputs'][node_id]
                    if 'images' in node_output:
                        images_output = []
                        for image in node_output['images']:
                            image_data = self.get_image(image['filename'], image['subfolder'], image['type'])
                            images_output.append(image_data)
                        output_images[node_id] = images_output

            if not output_images:
                raise ValueError("No images were generated.")
                
        finally:
            self.close_connection()

        return output_images

    
# Create output directory if it doesn't exist
output_dir = "./output"
os.makedirs(output_dir, exist_ok=True)

# Instantiate the ComfyUIClient
server_address = "66.114.112.70"
port = "11416"
client = ComfyUIClient(server_address, port)

def generate_image(prompt_text):
    print("Received prompt_text:", prompt_text)
    try:
        # Load the workflow JSON from file
        with open('workflow_api.json', 'r') as f:
            workflow = json.load(f)
        print("Loaded workflow:", workflow)

        # Find and update the 'pos_prompt' node (node "6")
        pos_prompt_node = workflow.get("6")
        if not pos_prompt_node:
            return "pos_prompt node not found in the workflow JSON."

        pos_prompt_node['inputs']['text'] = str(prompt_text)
        print("Updated pos_prompt node:", pos_prompt_node)

    except (json.JSONDecodeError, KeyError) as e:
        print("Error loading or updating the workflow JSON:", e)
        return f"Error loading or updating the workflow JSON: {e}"

    client.connect()
    print("Connected to ComfyUI server")
    try:
        images = client.get_images(workflow)
        print("Retrieved images:", images)
    except ValueError as e:
        return str(e)

    # Find and process the 'last_node' (node "9")
    last_node_images = images.get("9", [])
    if last_node_images:
        saved_image_paths = []
        for i, image_data in enumerate(last_node_images):
            image_path = os.path.join(output_dir, f"generated_image_{i}.png")
            with open(image_path, 'wb') as f:
                f.write(image_data)
            saved_image_paths.append(image_path)
            print(f"Image saved at: {image_path}")

        return saved_image_paths
    else:
        print("No images were generated.")
        return "No images were generated."

# Define the Gradio interface
iface = gr.Interface(
    fn=generate_image,
    inputs=gr.Textbox(lines=20, label="Prompt"),
    outputs=gr.Gallery(label="Generated Images", columns=2),
    title="ComfyUI Image Generator",
    description="Enter a prompt to generate images using ComfyUI."
)

# Launch the Gradio interface
iface.launch()