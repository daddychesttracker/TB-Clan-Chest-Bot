This works with browser and installed game. Requires resolution to be set at 1080p, if you want to use a different resolution you will need to replace the images in the asset folder with your own.
In the asset folder you need to replace check_profile.png with your own. (tbprofile_id.png is for a future update with profile switching if you have multiple accounts under one user). 
Runs best when the counter account is set to soldier and is run from the installable version of the game, it can be run with the account set as a different rank but there may be some artifacts. 

if you get an SSL error when trying to run, add this to imports in main_gui.py

added tesseract support, download the latest version before using. assumes installation location C:\Program Files\Tesseract-OCR\tesseract.exe

import ssl
ssl._create_default_https_context = ssl._create_unverified_context


1. Install requirements - pip install -r requirements.txt

2. Run main_gui.py

3. Go to calibration tab. Here you need to calibrate the readable area for chests, roster and events. You can ignore accounts for now (future update)

Chest example.

<img width="410" height="292" alt="image" src="https://github.com/user-attachments/assets/31bff9ef-4936-420d-8fdd-2b3a129275c2" />

Roster example.

<img width="521" height="287" alt="image" src="https://github.com/user-attachments/assets/37296e9a-0b35-4445-a1e3-42c9626b06cd" />

Event example.

<img width="526" height="325" alt="image" src="https://github.com/user-attachments/assets/bf2f7320-55b9-4e58-adee-f245e1d0ed5e" />


For chests counts and roster scanning you it will navigate itself as soon as you click start or based on your timers, event scans however need to be open on the page that you are scanning. 

If you are running this with dual monitors its best to have this on the second screen but if you are running from one you need to shrink the gui so that it doesnt cover any of the clan menu.
In the automation tab you can add a discord webhook that will send you notifications when it completes a count or errors out. 
When mapping chests you need to reference the template document for them to go to the correct places, however because im lazy and found it easier the points in the mapper do nothing. if you wish to change what points a chest is worth you need to change 
them in the template document.

<img width="994" height="973" alt="image" src="https://github.com/user-attachments/assets/8db400b7-aa53-4566-8821-3f7490b2fad8" />
<img width="992" height="976" alt="image" src="https://github.com/user-attachments/assets/57f2ed54-95cf-41f7-8cf0-4e28c750a7b1" />
<img width="996" height="977" alt="image" src="https://github.com/user-attachments/assets/806a16a9-6efb-474e-92d7-e9deebdddec3" />
<img width="990" height="974" alt="image" src="https://github.com/user-attachments/assets/76392caa-beaa-4721-b989-7bcc6aee780e" />
<img width="995" height="972" alt="image" src="https://github.com/user-attachments/assets/c56cce05-9a8a-49e3-8d4e-a8c511262643" />
<img width="995" height="979" alt="image" src="https://github.com/user-attachments/assets/f5458f01-f10f-4864-80da-a5a13e34e554" />











