import tensorflow as tf
from ..core.core import ImageAndVideo
from imutils import resize
import numpy as np
import cv2
import pickle
import os
from scipy.spatial import distance


class FaceIdentifier(ImageAndVideo):
    """
    Class used to identify a person based on input image.

    Arguments:
        encodings_location {str}:      
            Path to the pickle containing encodings. If the path
            specified does not exist the path will be created.
        embeding_model_location {str}:
            Path towards the tf lite model that will be used 
            to create the facial embeddings.


    Example of usage:
        face_embedding = FaceIdentifyDataCreation(encodings_location=encodings_location,
                                                  embeding_model_location=embeding_model_location)
        face_recognizer.start_video_stream()
        face_recognizer.capture_frame_and_recognize_faces(tolerance=tolerance, face_probability=face_probability)
        face_recognizer.display_predictions()
    """

    def __init__(self, encodings_location, embeding_model_location):

        super().__init__()

        self.encodings_location = encodings_location

        if os.path.isfile(encodings_location):
            self.encoded_faces = pickle.loads(open(encodings_location, "rb").read()) 
        else:
            data = {"encodings": [], "names": []}
            with open(encodings_location, "wb") as f:
                f.write(pickle.dumps(data))
            self.encoded_faces = pickle.loads(open(encodings_location, "rb").read()) 

        self.embedding_model = tf.lite.Interpreter(model_path=embeding_model_location)
        self.embedding_model.allocate_tensors()
        self.input_details = self.embedding_model.get_input_details()
        self.output_details = self.embedding_model.get_output_details()   

    def recognize_faces(self, tolerance=0.35):
        """
        This function recognizes the faces in a given image. In order to work, an
        image must first be loaded with either load_image_from_file or load_image_from_frame 
        and then the detect_faces function also need to be run.

        For ease of use, rather implement the capture_frame_and_recognize_faces function.


        Arguments:
            tolerance {float, default=0.35}:
                Minimum distance required to match a face. The lower the value
                the more constraint the matching will be.
        """
        
        boxes = [(y,w,x,h) for (x, y, w, h) in self.bounding_boxes]

        encodings = []
        for i,face in enumerate(self.faces):

            self.embedding_model.set_tensor(self.input_details[0]['index'], face)
            self.embedding_model.invoke()
            predicted_encoding = self.embedding_model.get_tensor(self.output_details[0]['index'])
            encodings.append(predicted_encoding[0])

        self.recognized_faces = []

        for encoding in encodings:
            encoding = encoding.reshape(1,-1)
            similarities = distance.cdist(self.encoded_faces["encodings"], encoding,'cosine')
            similarities = similarities/similarities.max()
            matches = [distance[0] <= tolerance for distance in similarities]

            if True in matches and sum(matches) >= 2:

                matchedIdxs = [i for (i, b) in enumerate(matches) if b]
                sims = {}
                counts = {}

                for i in matchedIdxs:
                    name = self.encoded_faces["names"][i]
                    counts[name] = counts.get(name, 0) + 1
                
                name = max(counts, key=counts.get)

                sims = {name:[] for name in np.unique(self.encoded_faces["names"])}

                for i in matchedIdxs:
                    similarity = similarities[i][0]
                    name = self.encoded_faces["names"][i]
                    sims[name].append(similarity)

                average_sim = {name:np.mean(sim)/(counts[name]**2) for name, sim in sims.items() if not np.isnan(np.mean(sim))}
                name = min(average_sim, key=average_sim.get)
            else:
                name = 'Unkown' 

            self.recognized_faces.append(name)

        self.colors = [(33, 33, 183) if name == "Unkown" else (0, 102, 0) for name in self.recognized_faces]
        self.labels = ['Unkown Person' if name == "Unkown" else  f'{name} identified' for name in self.recognized_faces]


    def capture_frame_and_recognize_faces(self, tolerance=0.35, face_probability=0.9):
        """
        Capture the current frame of the video stream and recognize the 
        people in question.

        Arguments:
            tolerance {float, default=0.35}:
                Minimum distance required to match a face. The lower the value
                the more constraint the matching will be.
            face_probability {float, default = 0.9}:
                Minimum probability required to say face is identified. 
        
        Returns:
            A list of names detected.
        """

        self.capture_frame_and_load_image()
        self.detect_faces(probability=face_probability, face_size=(160,160))
        self.recognize_faces(tolerance=tolerance)
        self.draw_boxes_around_faces()

        return self.recognized_faces

    def capture_frame_and_recognize_faces_live(self, tolerance=0.35, face_probability=0.9):

        """
        Start a video stream and and recognize the  people in question. To stop the video stream
        press Q.

        Arguments:
            tolerance {float, default=0.35}:
                Minimum distance required to match a face. The lower the value
                the more constraint the matching will be.
            face_probability {float, default = 0.9}:
                Minimum probability required to say face is identified. 
        """

        while True:

            # grab the frame from the threaded video stream and resize it to have a maximum width of 400 pixels
            frame = self.vs.read()
            frame = resize(frame, width=400)

            self.load_image_from_frame(frame)
            self.detect_faces(probability=face_probability, face_size=(160,160))
            self.recognize_faces(tolerance=tolerance)
            self.draw_boxes_around_faces()

            key = cv2.waitKey(1) & 0xFF
            cv2.imshow("Frame", cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB))
            # if the `q` key was pressed, break from the loop
            if key == ord("q"):
                break
                
        cv2.destroyAllWindows()

    def get_labels(self):

        return self.labels