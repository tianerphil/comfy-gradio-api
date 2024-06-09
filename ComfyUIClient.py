import websocket
import uuid
import json
import urllib.request
import urllib.parse
import os
import logging
import shutil
from requests_toolbelt.multipart.encoder import MultipartEncoder
import requests

# Set up logging
logging.basicConfig(
    # level=logging.DEBUG,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)'
)

class ComfyUIClient:
    def __init__(self, server_address, port, user_id=None):
        self.server_address = f"{server_address}:{port}"
        self.user_id = user_id if user_id else str(uuid.uuid4())
        self.ws = None
        self.workflow = None
        self.load_image_node_number = 0
        self.seed_node_number = 0
        self.positive_prompt_node_number = 0
        self.output_node_number = 0

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_connection()

    def connect(self):
        self.ws = websocket.WebSocket()
        self.ws.connect(f"ws://{self.server_address}/ws?clientId={self.user_id}")

    def close_connection(self):
        if self.ws:
            self.ws.close()
            self.ws = None

    def load_workflow(self, filepath, load_image_node_number, seed_node_number, positive_prompt_node_number, output_node_number):
        with open(filepath, 'r') as f:
            self.workflow = json.load(f)
        self.load_image_node_number = load_image_node_number
        self.seed_node_number = seed_node_number
        self.positive_prompt_node_number = positive_prompt_node_number
        self.output_node_number = output_node_number
        logging.debug("Loaded workflow: %s", self.workflow)
        logging.debug("Set node numbers - Load Image: %d, Seed: %d, Positive Prompt: %d, Output: %d",
                      self.load_image_node_number, self.seed_node_number, self.positive_prompt_node_number, self.output_node_number)

    def update_seed_node(self, seed_value):
        seed_node = self.workflow.get(str(self.seed_node_number))
        if not seed_node:
            raise ValueError(f"Seed node {self.seed_node_number} not found in the workflow JSON.")
        seed_node["inputs"]["seed"] = seed_value
        logging.debug("Updated seed node %s: %s", self.seed_node_number, seed_node)

    def update_positive_prompt(self, prompt_text):
        pos_prompt_node = self.workflow.get(str(self.positive_prompt_node_number))
        if not pos_prompt_node:
            raise ValueError(f"Positive prompt node {self.positive_prompt_node_number} not found in the workflow JSON.")
        pos_prompt_node['inputs']['text'] = str(prompt_text)
        logging.debug("Updated positive prompt node %s: %s", self.positive_prompt_node_number, pos_prompt_node)

    def upload_image(self, local_file_path, input_dir, image_type='input', overwrite=True):
        if not os.path.exists(input_dir):
            os.makedirs(input_dir)
        logging.debug("Start to upload_image input_dir=%s, image_type=%s, overwrite=%s", input_dir, image_type, overwrite)
        
        filename = os.path.basename(local_file_path)
        logging.debug("Resolved filename: %s", filename)
        
        destination_path = os.path.join(input_dir, filename)
        logging.debug("Destination path: %s", destination_path)
        
        shutil.copy(local_file_path, destination_path)
        logging.debug("Copied %s to %s", local_file_path, destination_path)
        
        with open(destination_path, 'rb') as file:
            multipart_data = MultipartEncoder(
                fields={
                    'image': (filename, file, 'image/png'),
                    'type': image_type,
                    'overwrite': str(overwrite).lower()
                }
            )
            headers = {'Content-Type': multipart_data.content_type}
            logging.debug("Headers prepared: %s", headers)
            
            response = requests.post(f"http://{self.server_address}/upload/image", data=multipart_data, headers=headers)
            logging.debug("Response status code: %s", response.status_code)
            logging.debug("Response content: %s", response.text)
            
            return response.json()

    def update_load_image_node(self, response):
        load_image_node = self.workflow.get(str(self.load_image_node_number))
        if not load_image_node:
            raise ValueError(f"Load image node {self.load_image_node_number} not found in the workflow JSON.")
        filename = response['name']
        # subfolder = response['subfolder'] #ignore subfolder since server side code does not use it
        load_image_node['inputs']['image'] = f"{filename}"
        logging.debug("Updated load image node %s: %s", self.load_image_node_number, load_image_node)

    def queue_prompt(self):
        p = {"prompt": self.workflow, "client_id": self.user_id}
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

    def get_images(self):
        prompt_id = self.queue_prompt()['prompt_id']
        logging.debug("Queued prompt ID: %s", prompt_id)
        
        output_images = {}
        try:
            while True:
                out = self.ws.recv()
                logging.debug("Received data from websocket: %s", out)
                
                if isinstance(out, str):
                    message = json.loads(out)
                    logging.debug("Decoded JSON message: %s", message)
                    
                    if message['type'] == 'executing':
                        data = message['data']
                        logging.debug("Executing data: %s", data)
                        
                        if data['node'] is None and data['prompt_id'] == prompt_id:
                            logging.debug("Execution is done for prompt ID: %s", prompt_id)
                            break  # Execution is done
                else:
                    logging.debug("Received binary data, continuing...")
                    continue  # previews are binary data

            history = self.get_history(prompt_id)[prompt_id]
            logging.debug("History for prompt ID %s: %s", prompt_id, history)
            
            for o in history['outputs']:
                logging.debug("Processing output node ID: %s", o)
                
                for node_id in history['outputs']:
                    node_output = history['outputs'][node_id]
                    logging.debug("Node output for node ID %s: %s", node_id, node_output)
                    
                    if 'images' in node_output:
                        images_output = []
                        for image in node_output['images']:
                            image_data = self.get_image(image['filename'], image['subfolder'], image['type'])
                            logging.debug("Retrieved image data size: %d", len(image_data))
                            
                            images_output.append(image_data)
                        output_images[node_id] = images_output

            if not output_images:
                logging.debug("No images were generated.")
                raise ValueError("No images were generated.")
                
        except Exception as e:
            logging.error("An error occurred: %s", e)
            raise
            
        finally:
            logging.debug("Closing connection.")
            self.close_connection()

        return output_images
