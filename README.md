RakanBot has two main functions

1) Data collection
- Calling !collect_all in a server will generate a csv file with most information available on the server. (Messages, reactions, time joined, etc.) 
- Automatically starting a survey for new members, collecting their demographic information, saved to students.csv

2) AI community manager chatbot
- Majority of the code is in LLM.py

SETUP 
1) Download this file structure in a local environment
2) You may need to install python 3.8.0, and all the libraries in requirements.txt
3) You will need the Discord keys (Get this from me), and a groq and exa key for the chatbot side to work.
4) running main.py should get the bot up and running


note to whichever poor soul that needs to read this: When I coded this, only god and I knew how it worked. Now, only god knows. There is probably a lot of junk which I don't know if is necessary for the bot to work. I profusely apologize. 

Further info: The bot is running on my old computer 24/7. That's the server. It's on windows 32 and hence you may find success in using a 32 bit interpreter instead of the 64 bit one. 

