import re
import sys
import os
from gtts import gTTS
from googletrans import Translator
from pydub import AudioSegment
import soundfile as sf
import pyrubberband as pyrb
import yt_dlp


def main():

    if len(sys.argv) == 1:
        print("Usage: python main.py <youtube link> -s <dir to subtitles> -l <target language>")
        return

    ytLink = sys.argv[1]

    ydl_opts = {
        'writesubtitles': True,
        # 'sub-lang': 'en',
        'allsubtitles': True,
        'skip_download': True,
        'outtmpl': os.path.join('srt', '%(id)s'),

    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(ytLink)

    id = info_dict.get('id')

    srtFileDir = None
    lang = None

    for i in range(2, len(sys.argv), 2):

        if sys.argv[i] == "-s":
            try:
                srtFileDir = sys.argv[i + 1]
            except FileNotFoundError:
                print("File not found")
                return

        elif sys.argv[i] == "-l":
            lang = sys.argv[i + 1]
            if not lang in ["", "en", "de", "fr", "es", "it", "pt", "nl", "pl", "ru", "tr", "ja", "ko", "zh"]:
                print("Language not supported")
                print(
                    "Supported languages: en, de, fr, es, it, pt, nl, pl, ru, tr, ja, ko, zh")
                return
            if lang == "":
                lang = "en"

    if srtFileDir == None:

        if os.path.exists(f"srt/{id}.{lang}.vtt"):
            srtFileDir = f"srt/{id}.{lang}.vtt"
        elif os.path.exists(f"srt/{id}.en.vtt"):
            srtFileDir = f"srt/{id}.en.vtt"
        # ToDo else find vtt file
        else:
            print("No subtitles found")
            return
        # print(srtFileDir)
    srtFile = open(srtFileDir, "r", encoding='utf-8')

    print("Youtube Auto Dubbing")

    # Read srt file
    audioList = makeAudioList(srtFile)

    # Translate
    translateAudioList(audioList, lang)

    # Gtts
    generateAudio(audioList, lang)

    # Matching
    matchingAudioToTime(audioList)

    combineAudio(audioList)


def makeAudioList(srtFile):
    print("Reading srt file...")
    audioList = []
    # First item is left empty
    audioList.append("nothing")

    i = 0
    for line in srtFile:

        line = line.strip()
        print(line)

        if re.match(r'^\d{2}:\d{2}:\d{2}[.,]\d{3} --> \d{2}:\d{2}:\d{2}[.,]\d{3}$', line):
            i += 1
            start = line[:12]
            end = line[17:]

            audioList.append({
                "start": start,
                "end": end,
                "text": ""
            })

        elif len(line) > 0 and i != 0 and line != f"{i+1}":

            audioList[i]["text"] = audioList[i]["text"] + " " + line

    return audioList


def generateAudio(audioList, lang):
    print("Generating audio...")
    index = 1
    for audio in audioList:
        if audio != "nothing":

            tts = gTTS(audio["text"], lang=lang)
            tts.save(f"audio/{index}.mp3")
            mp3ToWav(f"audio/{index}.mp3")
            print(f"{index}/{len(audioList)-1}")
            index += 1
    return audioList


def translateAudioList(audioList, lang):
    # ToDo instead of translating audioList translate entire file for more context
    print("Translating audio...")
    index = 1
    translator = Translator()
    for audio in audioList:
        if audio != "nothing":
            audio["text"] = translator.translate(audio["text"], dest=lang).text

            print(f"{index}/{len(audioList)-1}")
            index += 1
    return audioList


def matchingAudioToTime(audioList):
    print("Matching audio to time...")
    index = 1
    for audio in audioList:
        if audio != "nothing":

            start = ((int(audio["start"][:2])*3600) +
                     (int(audio["start"][3:5]) * 60) +
                     int(audio["start"][6:8]) +
                     float("0." + audio["start"][9:12]))

            end = ((int(audio["end"][:2])*3600) +
                   (int(audio["end"][3:5]) * 60) +
                   int(audio["end"][6:8]) +
                   float("0." + audio["end"][9:12]))

            desiredDuration = end - start
            # print(f"desiredDuration: {desiredDuration}")

            audioFile = AudioSegment.from_file(f"audio/{index}.wav")
            audioDuration = len(audioFile) / 1000.0
            # print("audioDuration: ", audioDuration)

            ratio = desiredDuration/audioDuration
            # print(f"Ratio: {ratio}")

            data, samplerate = sf.read(f"audio/{index}.wav")
            y_stretch = pyrb.time_stretch(data, samplerate, (1/ratio))
            sf.write(f"audio/{index}.wav", y_stretch, samplerate, format='wav')

            print(f"{index}/{len(audioList)-1}")
            index += 1


def mp3ToWav(audioDIrMp3):
    audio = AudioSegment.from_mp3(audioDIrMp3)
    audioDIrWav = audioDIrMp3.replace(".mp3", ".wav")
    audio.export(audioDIrWav, format="wav")
    os.remove(audioDIrMp3)


def combineAudio(audioList):
    print("Combining audio...")
    index = 1

    endOfVideo = ((int(audioList[-1]["end"][:2])*3600) +
                  (int(audioList[-1]["end"][3:5]) * 60) +
                  int(audioList[-1]["end"][6:8]) +
                  float("0." + audioList[-1]["end"][9:12]))

    combinedAudio = AudioSegment.silent(duration=(endOfVideo*1000))
    for audio in audioList:
        if audio != "nothing":
            start = ((int(audio["start"][:2])*3600) +
                     (int(audio["start"][3:5]) * 60) +
                     int(audio["start"][6:8]) +
                     float("0." + audio["start"][9:12]))

            combinedAudio = combinedAudio.overlay(AudioSegment.from_file(
                f"audio/{index}.wav"), position=(start*1000))

            print(f"{index}/{len(audioList)-1}")
            index += 1
    combinedAudio.export("finall.wav", format="wav")

    deleteAllFilesInFolder("audio")


def deleteAllFilesInFolder(dir):
    for file in os.listdir(dir):
        os.remove(f"audio/{file}")


main()
