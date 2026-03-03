import os
import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog, scrolledtext
import pywhatkit
import cv2
from cvzone.HandTrackingModule import HandDetector
import geocoder
import boto3
import webbrowser
import requests
import cohere
import io
import base64

# Initialize Boto3 client for EC2 and S3
ec2_client = boto3.client('ec2')
s3_client = boto3.client('s3')

# Initialize Cohere client
COHERE_API_KEY = #yourkey
cohere_client = cohere.Client(COHERE_API_KEY)

# Initialize SerpAPI key
SERPAPI_API_KEY = '#yourkey'

# Initialize Google Vision API key
VISION_API_KEY = '#yourapikey'

def describe_image(image_path):
    try:
        # Load the image into memory
        with io.open(image_path, 'rb') as image_file:
            content = image_file.read()

        # Encode image to base64
        encoded_image = base64.b64encode(content).decode('utf-8')

        # Prepare the request payload
        request_payload = {
            "requests": [
                {
                    "image": {
                        "content": encoded_image
                    },
                    "features": [
                        {
                            "type": "LABEL_DETECTION",
                            "maxResults": 10  # Adjust the number of results as needed
                        }
                    ]
                }
            ]
        }

        # Make the request to the Vision API
        url = f'https://vision.googleapis.com/v1/images:annotate?key={VISION_API_KEY}'
        response = requests.post(url, json=request_payload)

        # Check if the request was successful
        if response.status_code != 200 or 'error' in response.json():
            raise Exception(f"Error {response.status_code}: {response.json().get('error', {}).get('message', 'Unknown error')}")

        # Parse the response
        label_annotations = response.json()['responses'][0].get('labelAnnotations', [])

        # Check if any labels were found
        if not label_annotations:
            return "No labels detected."

        # Collect the labels
        labels = [label['description'] for label in label_annotations]
        prompt = f"Based on the image labels: {' '.join(labels)}\nGenerate a summary:"

        # Generate text using Cohere
        summary = generate_text_with_cohere(prompt)

        return summary

    except Exception as e:
        return str(e)

def select_image():
    # Open file dialog to select an image file
    image_path = filedialog.askopenfilename(filetypes=[("Image Files", ".jpg;.jpeg;*.png")])
    if image_path:
        result = describe_image(image_path)
        result_text.delete(1.0, tk.END)
        result_text.insert(tk.END, result)

def send_email():
    sender_email = os.environ.get('SENDER_EMAIL')
    password = os.environ.get('EMAIL_PASSWORD')

    if not sender_email or not password:
        messagebox.showerror("Configuration Error", "SENDER_EMAIL and EMAIL_PASSWORD environment variables must be set.")
        return

    receiver_email = simpledialog.askstring("Receiver Email", "Enter receiver's email:")
    message = simpledialog.askstring("Message", "Enter your message:")
    subject = 'DOSS Technical Training Project'

    try:
        pywhatkit.send_mail(sender_email, password, subject, message, receiver_email)
        messagebox.showinfo("Success", "Email sent successfully!")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to send email: {str(e)}")

def get_location_info():
    coordinate = geocoder.ip('me').latlng
    city = geocoder.osm(coordinate, method='reverse').city
    nearby_places = geocoder.osm(coordinate, method='reverse').json['address']

    location_info = f"City: {city}\nNearby Places: {nearby_places}"
    messagebox.showinfo("Location Info", location_info)

def capture_hand_gestures():
    model = HandDetector()
    cap = cv2.VideoCapture(0)

    while True:
        status, photo = cap.read()
        hand = model.findHands(photo)
        cv2.imshow("Hand Gestures", photo)
        if cv2.waitKey(10) == 13:
            break

    cv2.destroyAllWindows()
    cap.release()

def list_ec2_instances():
    response = ec2_client.describe_instances()
    instance_ids = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            state = instance['State']['Name']
            print(f"Instance ID: {instance_id}, State: {state}")
            instance_ids.append(instance_id)
    instance_ids_str = '\n'.join(instance_ids)
    messagebox.showinfo("EC2 Instance IDs", f"Instance IDs:\n{instance_ids_str}")

def stop_ec2_instance():
    response = ec2_client.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])
    instances = response['Reservations']

    if not instances:
        messagebox.showinfo("No Running Instances", "There are no running instances to stop.")
        return

    instance_number = simpledialog.askinteger("Select Instance", "Enter 1 to stop the instance:") - 1

    if instance_number is None or instance_number < 0 or instance_number >= len(instances):
        messagebox.showerror("Invalid Selection", "Please select a valid instance number.")
        return

    selected_instance_id = instances[instance_number]['Instances'][0]['InstanceId']
    ec2_client.stop_instances(InstanceIds=[selected_instance_id])
    messagebox.showinfo("Instance Stopped", f"Stopping instance {selected_instance_id}")

def launch_instance():
    response = ec2_client.run_instances(
        ImageId='ami-09298640a92b2d12c',  # Replace with your desired AMI ID
        InstanceType='t2.micro',  # Replace with your desired instance type
        MinCount=1,
        MaxCount=1
    )
    instance_id = response['Instances'][0]['InstanceId']
    print(f"New instance launched with ID: {instance_id}")

def open_url():
    webbrowser.open("http://3.109.103.64:10001/")

def upload_to_s3():
    file_path = filedialog.askopenfilename()
    if file_path:
        key = simpledialog.askstring("Key", "Enter the key (name) for the file in the bucket:")
        try:
            s3_client.upload_file(file_path, "dossttpprojectbucket", key)
            messagebox.showinfo("Success", "File uploaded successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to upload file: {str(e)}")

def download_from_s3():
    key = simpledialog.askstring("Key", "Enter the key (name) of the file to download from the bucket:")
    if key:
        file_path = filedialog.asksaveasfilename(initialfile=key.split('/')[-1])
        if file_path:
            try:
                s3_client.download_file("dossttpprojectbucket", key, file_path)
                messagebox.showinfo("Success", "File downloaded successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to download file: {str(e)}")

def delete_from_s3():
    key = simpledialog.askstring("Key", "Enter the key (name) of the file to delete from the bucket:")
    if key:
        try:
            s3_client.delete_object(Bucket="dossttpprojectbucket", Key=key)
            messagebox.showinfo("Success", "File deleted successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete file: {str(e)}")

def search_serpapi(query):
    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_API_KEY
    }
    response = requests.get("https://serpapi.com/search", params=params)
    return response.json()

def generate_text_with_cohere(prompt):
    response = cohere_client.generate(
        model='command-light-nightly',
        prompt=prompt,
        max_tokens=50,
        temperature=0.75,
    )
    return response.generations[0].text.strip()

def search_and_generate(query):
    search_results = search_serpapi(query)
    search_snippets = [result.get('snippet', '') for result in search_results.get('organic_results', [])]
    combined_snippets = "\n".join(search_snippets)
    cohere_prompt = f"Based on the following information, write a summary:\n\n{combined_snippets}"
    summary = generate_text_with_cohere(cohere_prompt)
    return summary

def chatbot():
    chat_window = tk.Toplevel(root)
    chat_window.title("Chatbot")
    chat_window.configure(bg='lightblue')

    def get_response():
        query = query_entry.get()
        summary = search_and_generate(query)
        response_area.insert(tk.END, f"Q: {query}\nA: {summary}\n\n")
        query_entry.delete(0, tk.END)

    query_label = tk.Label(chat_window, text="Enter your query:", bg='lightblue')
    query_label.pack(pady=5)

    query_entry = tk.Entry(chat_window, width=50)
    query_entry.pack(pady=5)

    response_area = scrolledtext.ScrolledText(chat_window, wrap=tk.WORD, width=60, height=20)
    response_area.pack(pady=5)

    submit_button = tk.Button(chat_window, text="Get Response", command=get_response, bg='blue', fg='white')
    submit_button.pack(pady=5)

# Main Window
root = tk.Tk()
root.title("Main Window")
root.configure(bg='lightgrey')

buttons = [
    ("Send Email", send_email),
    ("Get Location Info", get_location_info),
    ("Capture Hand Gestures", capture_hand_gestures),
    ("List EC2 Instances", list_ec2_instances),
    ("Stop EC2 Instance", stop_ec2_instance),
    ("Launch EC2 Instance", launch_instance),
    ("Open URL", open_url),
    ("Upload to S3", upload_to_s3),
    ("Download from S3", download_from_s3),
    ("Delete from S3", delete_from_s3),
    ("Chatbot", chatbot),
    ("Image Detection", select_image)  # Add the image detection button
]

# Create a text widget to display the results of image detection
result_text = tk.Text(root, width=60, height=20, wrap=tk.WORD)
result_text.pack(pady=5)

for btn_text, command in buttons:
    btn = tk.Button(root, text=btn_text, command=command, bg='blue', fg='white')
    btn.pack(pady=5, padx=10)

root.mainloop()  
