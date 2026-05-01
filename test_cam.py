import cv2
from ultralytics import YOLO

# تحميل العقل 
model = YOLO('best.pt')

cap = cv2.VideoCapture(0)

# إعدادات السرعة
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

print("Starting SiteSentry (1-Meter Range)... Press 'q' to exit.")

frame_count = 0
last_results = None

while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to grab frame")
        break

    frame_count += 1

    # الخدعة لمسافة متر:
    # imgsz=320 (حجم صغير وسريع جداً لأن السوكيت قريب وواضح)
    # conf=0.4 (الروبوت لازم يكون متأكد 40% وفوق عشان يرسم المربع)
    if frame_count % 2 != 0 or last_results is None:
        last_results = model.predict(frame, conf=0.4, imgsz=320, verbose=False)

    annotated_frame = last_results[0].plot()

    cv2.imshow("SiteSentry - 1 Meter Demo", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()