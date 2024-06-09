import os
import gradio as gr
import logging
import random
from ComfyUIClient import ComfyUIClient

# Set up logging
logging.basicConfig(
    #level=logging.DEBUG,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)'
)

# Global variables
input_dir = "./input"
output_dir = "./output"
workflow_template = 'i2i_workflow_api.json'

# Create output directory if it doesn't exist
os.makedirs(output_dir, exist_ok=True)

# Instantiate the ComfyUIClient
server_address = "66.114.112.70"
port = "20407"

def image_generate_image(local_image, prompt_text):
    logging.debug("Received prompt_text: %s", prompt_text)
    logging.debug("Received local_image: %s", local_image)
    try:
        with ComfyUIClient(server_address=server_address, port=port) as client:
            # Upload the image
            logging.debug("Uploading image...")
            upload_response = client.upload_image(local_image, input_dir)
            logging.debug("Upload response: %s", upload_response)

            # Load and update the workflow
            logging.debug("Loading workflow from %s...", workflow_template)
            client.load_workflow(
                filepath=workflow_template,
                load_image_node_number=72,
                seed_node_number=63,
                positive_prompt_node_number=66,
                output_node_number=69
            )
            logging.debug("Workflow loaded successfully.")
            
            logging.debug("Updating load image node...")
            client.update_load_image_node(upload_response)
            logging.debug("Load image node updated.")

            logging.debug("Updating seed node...")
            client.update_seed_node(random.randint(1, 1500000))
            logging.debug("Seed node updated.")

            logging.debug("Updating positive prompt node...")
            client.update_positive_prompt(prompt_text)
            logging.debug("Positive prompt node updated.")

            logging.debug("Requesting images...")
            images = client.get_images()
            logging.debug("Images retrieved successfully.")
            
            # Log the structure and content of the images dictionary
            for node_id, image_list in images.items():
                logging.debug("Node ID: %s, Number of Images: %d", node_id, len(image_list))
                for idx, img in enumerate(image_list):
                    logging.debug("Image %d: %d bytes", idx, len(img))

            # Process the 'output_node'
            output_node_images = images.get(str(client.output_node_number), [])
            logging.debug("Retrieved %d images from the output node.", len(output_node_images))
            if output_node_images:
                saved_image_paths = []
                for i, image_data in enumerate(output_node_images):
                    image_path = os.path.join(output_dir, f"generated_image_{i}.png")
                    with open(image_path, 'wb') as f:
                        f.write(image_data)
                    saved_image_paths.append(image_path)
                    logging.debug("Image saved at: %s", image_path)

                return saved_image_paths
            else:
                logging.debug("No images were generated.")
                return "No images were generated."

    except Exception as e:
        logging.error("An error occurred: %s", e)
        return str(e)

# Define the Gradio interface with two inputs: a local image and a text prompt
iface = gr.Interface(
    fn=image_generate_image,
    inputs=[
        gr.Image(type="filepath", label="Upload Image"),
        gr.Textbox(lines=20, label="Prompt")
    ],
    outputs=gr.Gallery(label="Generated Images", columns=2),
    title="ComfyUI Image Generator",
    description="Upload an image and enter a prompt to generate images using ComfyUI."
)

# Launch the Gradio interface
iface.launch()
