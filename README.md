# AutoTube
Python pipeline to automatically create YouTube shorts.


Scrape top posts across any subreddit using reddit’s python library PRAW

Send the text to ChatGPT o4-mini to analyze if it would be a good short; if it would, omit random information and side tangents.

Send the script and title to eleven labs to do the voiceover. Convert mp3 to wav.

Use openai’s whisperX speech transcription model to make a json with the times of every word in the script against the eleven labs audio. ElevenLabs actually does have an option to return a json but i wanted to build something that would work if i can find a cheaper alternative to ElevenLabs.

Group the words into phrases and use ffmpeg to: replace the audio in my old minecraft video gameplay with the voiceover and burn the words onto the video at the times established by whisperX. Also, title
