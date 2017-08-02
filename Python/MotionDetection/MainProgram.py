import time
#time.sleep(30)
import cv2
import datetime
import imutils
import math
import multiprocessing
import os
import email.mime.multipart
import email.mime.base
import email.mime.text
import email.encoders
import smtplib
#In the camera loop function we loop over and over, recieving images from the video stream on the 
#camera and checking to see if any motion has occoured, and if it has, sending an email wih the captured images.
def GetBlurredGreyscale(image):
    return cv2.GaussianBlur(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (21, 21), 0)
def GetContours(prev_image, cur_image):
    frame_delta = cv2.absdiff(prev_image, cur_image)
    threshold = cv2.dilate(cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1], None, iterations=2)
    return cv2.findContours(threshold.copy(), cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
def CameraLoop( queue, min_contour_area=500, dwell_time=5, max_video_length=15):
    camera = cv2.VideoCapture(0)
    print(camera)
    prev_frame = None
    video_started = False
    time_video_started = None
    video_frames = []
    time_motion_last_detected = None
    while True:
        #In the below line, we grab the frame from the initialized camera object.
        (grabbed, frame) = camera.read()
        text = 'unoccupied'
        if not grabbed:
            break
        small_frame = imutils.resize(frame, width=250)
        scale_factor = frame.shape[1]/small_frame.shape[1]
        blurred_grayscale_image = GetBlurredGreyscale(small_frame)
        if prev_frame is None:
            prev_frame = blurred_grayscale_image
        (image, cnts, hierarchy) = GetContours(prev_frame, blurred_grayscale_image)
        if len(cnts) > 0:
            if not video_started:            
                video_started = True
                time_video_started = time.time()
            time_motion_last_detected = time.time()
            for c in cnts:
                if cv2.contourArea(c) < min_contour_area:
                    continue
                (x, y, w, h) = cv2.boundingRect(c)
                cv2.rectangle(frame, (math.floor(x*scale_factor), math.floor(y*scale_factor)), (math.floor((x + w)*scale_factor), math.floor((y + h)*scale_factor)), (0, 255, 0), 2)
                text = "Occupied"
        cv2.putText(frame, "Room Status: {}".format(text), (10, 20),cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        cv2.putText(frame, datetime.datetime.now().strftime("%A %d %B %Y %I:%M:%S%p"),(10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)
        #cv2.imshow("Security Feed", frame)
        key = cv2.waitKey(100)
        if key == ord('q'):
            break
        prev_frame = blurred_grayscale_image
        if video_started:
            video_frames.append(frame)
        if time_video_started and time_motion_last_detected and video_started and (time.time() - time_motion_last_detected > dwell_time or time.time() - time_video_started > max_video_length):
            video_started = False
            while True:
                try:
                    queue.put_nowait(video_frames)
                except:
                    pass
                else:
                    print('Sending Video')
                    video_frames = []
                    break
    cv2.destroyAllWindows()
    camera.release()
    queue.put("<<END>>")
def Build_Video(in_queue):
    if not os.path.isdir('/home/pi/Videos/Motion_Detection'):
        try:
            os.makedirs('/home/pi/Videos/Motion_Detection')
        except:
            print("Cannot make {0} directory, are you running as root? (sudo)".format('/home/pi/Video/Motion_Detection'))
    while True:
        if in_queue.empty():
            pass
        else:
            try:
                video_frames = in_queue.get_nowait()
            except:
                pass
            else:
                if video_frames and len(video_frames) > 0:
                    if video_frames == "<<END>>":
                        break
                    timestamp = datetime.datetime.now().strftime("%A_%d_%B_%Y_%I_%M_%S%p")
                    filename = "/home/pi/Videos/Motion_Detection/{0}.avi".format(timestamp)
                    print("Width: {0} Height: {1}".format(video_frames[0].shape[0],video_frames[0].shape[1]))
                    RAW_Video = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc(*'MJPG'), 10, (video_frames[0].shape[1],video_frames[0].shape[0]), True)
                    print("The video file stream is open.")
                    #print("There are {0} frames. Frame sizes are:".format(len(video_frames)))
                    #for frame in video_frames:
                        #print("{0} x {1} with {2} channels".format(frame.shape[0], frame.shape[1], frame.shape[2]))
                    for frame in video_frames:
                        RAW_Video.write(frame)
                    RAW_Video.release()
                    Send_Email(sender='yourraspberrypi@thefortress.com', recipients=['edgubala@gmail.com'], attachments=[filename])
def Send_Email(sender, recipients, attachments):
    msg = email.mime.multipart.MIMEMultipart()
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    msg['Date'] = datetime.datetime.now().strftime("%A %d %B %Y %I:%M:%S%p")
    msg['Subject'] = 'Motion detected on your Pi spycam'
    msg_body = email.mime.text.MIMEText('Please see the attachment, your security system has detected motion behaviour in its scanning viscinity.')
    for attachment in attachments:
        video_attachment = email.mime.base.MIMEBase('application', 'octet-stream')
        RAW_Video = open(attachment, 'rb')
        video_attachment.set_payload(RAW_Video.read())
        email.encoders.encode_base64(video_attachment)
        video_attachment.add_header('Content-Disposition', "attachment; filename=\"{0}\"".format(os.path.basename(attachment)))
        msg.attach(video_attachment)
    send_server = smtplib.SMTP('smtp.gmail.com', port=587)
    send_server.ehlo()
    send_server.starttls()
    send_server.ehlo
    send_server.login('thefortressraspberrypi@gmail.com', '1025CrossCountry')
    #send_server = smtplib.SMTP('localhost')
    send_server.sendmail('thefortressraspberrypi@gmail.com', recipients, msg.as_string())
    send_server.close()
    print("Notified {0}".format(recipients))
if __name__ == "__main__":
    print("main fucntion started")
    Video_Frames_Queue = multiprocessing.Queue(1)
    VisionProcess = multiprocessing.Process(target=CameraLoop, args=([Video_Frames_Queue, 50]))
    VideoSaveAndEmailProcess = multiprocessing.Process(target=Build_Video, args=([Video_Frames_Queue]))
    VisionProcess.start()
    print("processes started")
    VideoSaveAndEmailProcess.start()
    
    VisionProcess.join()
    VideoSaveAndEmailProcess.join()
