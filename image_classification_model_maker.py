# docker run --ipc=host --ulimit memlock=-1 --rm --gpus all -v "$(pwd)":"$(pwd)" nvcr.io/nvidia/tensorflow:23.02-tf2-py3
# on ubuntu 22.04 with rtx 2060
import autokeras as ak
import tensorflow as tf
from pathlib import Path
from PIL import Image
import imghdr
import os
dir = "./Data-V2/Training Data"
genre = os.listdir(dir)
print(genre)
image_extensions = [".png", ".jpg"]  # add there all your images file extensions
img_type_accepted_by_tf = ["bmp", "gif", "jpeg", "png"]

for i in genre:
    data_dir = f"{dir}/{i}"
    print(data_dir)
    for filepath in Path(data_dir).rglob("*"):
        if filepath.suffix.lower() in image_extensions:
            img_type = imghdr.what(filepath)
            if img_type is None:
                print(f"{filepath} is not an image")
                os.remove(filepath)
            elif img_type == "webp":
                print(f"{filepath} is a {img_type}, converting to png")
                with open("./invalid.txt", "w") as f:
                    f.write(f"{filepath} is a {img_type}, converting to png")
                im = Image.open(filepath)
                rgb_im = im.convert('RGB')
                rgb_im.save(f"{filepath}.png")
                os.remove(filepath)
            elif img_type not in img_type_accepted_by_tf:
                print(f"{filepath} is a {img_type}, not accepted by TensorFlow")
                with open("./invalid.txt", "w") as f:
                    f.write(f"{filepath} is a {img_type}, not accepted by TensorFlow") 
                os.remove(filepath)
train = ak.image_dataset_from_directory(
    directory=dir,
)
clf = ak.ImageClassifier(
    max_trials=10,
    overwrite=False,
    directory='./model',
    distribution_strategy=tf.distribute.MirroredStrategy(),    
)
clf.fit(train)
model = clf.export_model()
try:
    model.save('./model')
except:
    pass
