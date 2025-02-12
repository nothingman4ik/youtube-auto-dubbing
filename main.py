import re
import sys
import os
from gtts import gTTS
from googletrans import Translator
from pydub import AudioSegment
import soundfile as sf
import pyrubberband as pyrb
import yt_dlp
import shutil
import subprocess


def main():

    if len(sys.argv) == 1:
        print("Usage: python main.py <youtube link> -s <dir to subtitles> -l <target language>")
        return
    try:
        shutil.rmtree("tmp")
    except:
        pass
    os.makedirs("tmp/yt", exist_ok=True)
    os.makedirs("tmp/audio", exist_ok=True)

    ytLink = sys.argv[1]

    ydl_opts = {
        'writesubtitles': True,
        # 'sub-lang': 'en',
        'allsubtitles': True,
        'skip_download': False,
        'outtmpl': os.path.join('tmp/yt', '%(id)s'),
        'quiet': True,
        'merge_output_format': 'mp4',

    }

    subsFileDir = None
    lang = None

    for i in range(2, len(sys.argv), 2):

        if sys.argv[i] == "-s":
            try:
                subsFileDir = sys.argv[i + 1]
            except FileNotFoundError:
                print("File not found")
                return

        elif sys.argv[i] == "-a":
            ydl_opts["skip_download"] = True

        elif sys.argv[i] == "-l":
            lang = sys.argv[i + 1]
            if not lang in ["", "en", "de", "fr", "es", "it", "pt", "nl", "pl", "ru", "tr", "ja", "ko", "zh", "uk"]:
                print("Language not supported")
                print(
                    "Supported languages: en, de, fr, es, it, pt, nl, pl, ru, tr, ja, ko, zh")
                return

    if lang == None or lang == "":
        lang = "en"

    version = "1.1"
    print("---Youtube Auto Dubbing---")
    print(f"Version: {version}, by @mikk0")
    print("https://github.com/Mikk0git/youtube-auto-dubbing")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(ytLink)

    id = info_dict.get('id')
    if subsFileDir == None:

        if os.path.exists(f"tmp/yt/{id}.{lang}.vtt"):
            subsFileDir = f"tmp/yt/{id}.{lang}.vtt"
        elif os.path.exists(f"tmp/yt/{id}.en.vtt"):
            subsFileDir = f"tmp/yt/{id}.en.vtt"
        # ToDo else find vtt file
        else:
            print("No subtitles found")
            return

    os.makedirs(f"output/{id}", exist_ok=True)

    if subsFileDir == f"tmp/yt/{id}.{lang}.vtt":
        subsFile = open(subsFileDir, "r", encoding='utf-8')
        shutil.copyfile(subsFileDir, f"output/{id}/{id}.{lang}.vtt")
    else:
        # Translate
        subsFile = translateAudioList(subsFileDir, lang, id)

    print(f"ID: {id}")
    print(f"Language: {lang}")

    # Read srt file
    audioList = makeAudioList(subsFile)

    subsFile.close()

    # Gtts
    generateAudio(audioList, lang)

    # Matching
    matchingAudioToTime(audioList)

    combineAudio(audioList, id)

    if ydl_opts["skip_download"] == False:
        combineVideo(id)

    try:
        shutil.rmtree("tmp")
    except:
        pass


def makeAudioList(subsFile):
    print("Reading subtitle file")
    audioList = []
    # First item is left empty
    # ToDO Its time to change it
    audioList.append("nothing")

    i = 0
    for line in subsFile:

        line = line.strip()

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
    print("Generating audio")
    index = 1
    for audio in audioList:
        if audio != "nothing":
            try:
                tts = gTTS(audio["text"], lang=lang)
                tts.save(f"tmp/audio/{index}.mp3")
                mp3ToWav(f"tmp/audio/{index}.mp3")
                print(f"{index}/{len(audioList)-1}", end='\r')
            except:
                silence = AudioSegment.silent(duration=1000)
                silence.export(f"tmp/audio/{index}.wav", format="wav")

            index += 1
    return audioList


def translateAudioList(subsFileDir, lang, id):
    print("Translating subtitles")
    index = 1
    numberOfLines = countLines(subsFileDir)
    translator = Translator()
    subsFile = open(subsFileDir, "r", encoding='utf-8')
    translatedSubsFileDir = f"output/{id}/{id}.{lang}.vtt"
    translatedSubsFile = open(translatedSubsFileDir, "w", encoding='utf-8')
    for line in subsFile:

        if (not re.match(r'^\d{2}:\d{2}:\d{2}[.,]\d{3} --> \d{2}:\d{2}:\d{2}[.,]\d{3}$', line)
            and len(line) > 0
                and line != "WEBVTT\n"
                and "Kind:" not in line
                and "Language:" not in line
            ):

            translatedLine = translator.translate(line, dest=lang).text
            translatedSubsFile.write(translatedLine + '\n')
        elif "Language:" in line:
            translatedSubsFile.write(f"Language: {lang}\n")
        else:
            translatedSubsFile.write(line)

        print(f"{index}/{numberOfLines}", end='\r')
        index += 1
    subsFile.close()
    translatedSubsFile.close()

    translatedSubsFile = open(translatedSubsFileDir, "r", encoding='utf-8')
    return translatedSubsFile


def matchingAudioToTime(audioList):
    print("Matching audio to time")
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

            audioFile = AudioSegment.from_file(f"tmp/audio/{index}.wav")
            audioDuration = len(audioFile) / 1000.0
            # print("audioDuration: ", audioDuration)

            ratio = desiredDuration/audioDuration
            # print(f"Ratio: {ratio}")

            data, samplerate = sf.read(f"tmp/audio/{index}.wav")
            y_stretch = pyrb.time_stretch(data, samplerate, (1/ratio))
            sf.write(f"tmp/audio/{index}.wav",
                     y_stretch, samplerate, format='wav')

            print(f"{index}/{len(audioList)-1}", end='\r')
            index += 1


def mp3ToWav(audioDIrMp3):
    audio = AudioSegment.from_mp3(audioDIrMp3)
    audioDIrWav = audioDIrMp3.replace(".mp3", ".wav")
    audio.export(audioDIrWav, format="wav")
    os.remove(audioDIrMp3)


def combineAudio(audioList, id):
    print("Combining audio")
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
                f"tmp/audio/{index}.wav"), position=(start*1000))

            print(f"{index}/{len(audioList)-1}", end='\r')
            index += 1
    combinedAudio.export(f"output/{id}/{id}.wav", format="wav")


def combineVideo(id):
    print("Combining video")

    input_video = f'tmp/yt/{id}.mp4'
    input_audio = f'output/{id}/{id}.wav'
    output_video = f'output/{id}/{id}.mp4'

    ffmpeg_command = [
        'ffmpeg',
        '-v', 'error',
        '-i', input_video,
        '-i', input_audio,
        '-c:v', 'copy',
        '-map', '0:v:0',
        '-map', '1:a:0',
        '-shortest',
        output_video
    ]

    try:
        subprocess.run(ffmpeg_command, check=True)
        print(f'Done')
    except subprocess.CalledProcessError as e:
        print(f'Error adding audio to {input_video}: {e}')


def countLines(filename):
    i = 0
    with open(filename, "r", encoding="utf-8") as file:
        return sum(1 for _ in file)


main()
