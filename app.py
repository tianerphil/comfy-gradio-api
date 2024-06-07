import os
import json
import gradio as gr
import urllib.request
import urllib.parse
import uuid
import websocket
import logging
import random
from ComfyUIClient import ComfyUIClient

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Create output directory if it doesn't exist
output_dir = "./output"
os.makedirs(output_dir, exist_ok=True)

# Instantiate the ComfyUIClient
server_address = "66.114.112.70"
port = "13152"

def generate_image(prompt_text):
    print("Received prompt_text:", prompt_text)
    try:
        with ComfyUIClient(server_address=server_address, port=port) as client:
            client.load_workflow('workflow_api.json')

            # Update seed and positive prompt nodes
            client.update_seed_node(3, random.randint(1, 1500000))
            client.update_positive_prompt(6, prompt_text)

            images = client.get_images()

            # Process the 'last_node' (node "9")
            last_node_images = images.get("9", [])
            print(f"Retrieved {len(last_node_images)} images!" )
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

    except Exception as e:
        return str(e)

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
