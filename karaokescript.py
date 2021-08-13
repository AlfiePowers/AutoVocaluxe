# Auto karaoke creation software for Vocaluxe
# This has multiple dependencies - Refer to requirements.txt to verify they are installed

# Python imports
import subprocess
import sys, os, getopt, csv, math, re
import json
import time, datetime
import glob

# Audio based imports
from pydub import AudioSegment, effects, utils
from pydub.silence import split_on_silence, detect_nonsilent
from ffprobe import FFProbe
from tempocnn.classifier import TempoClassifier
from tempocnn.feature import read_features
from spleeter.separator import Separator
from spleeter.audio.adapter import AudioAdapter
import crepe
import audio2numpy as a2n
import pysrt
import youtube_dl
import webvtt

import pandas as pd

# Imports from this projects
import ultrastarUtils


# Class to manage the new song that we are creating
class UltrastarSong:
    details = {
        "song_file": "",
        "subtitles": "",
        "song_name": "",
        "bpm": 120,
        "song_length": 0
    }

    # Called when we create a new ultrastar song from a file, simply fills in all of the data
    def __init__(self, argv):
        # Clean up any of the pre-existing generated files
        for file in glob.glob('temp.mp3'):
            os.remove(file)
        for file in glob.glob('temp.mp3.*.vtt'):
            os.remove(file)

        # Attempt to load in the data from the command line if this is CLI program
        try:
            opts, args = getopt.getopt(argv, "hi:y:s", ["ifile=", "sfile=", "yfile="])
        except getopt.GetoptError:
            print("createKaraoke.py -i <inputSongFile> -s <subtitleFile>")
            sys.exit(2)
        for opt, arg in opts:
            if opt == '-h':
                print("createKaraoke.py -i <inputSongFile> -s <subtitleFile>")
                sys.exit()
            elif opt in ('-i', "--ifile"):
                self.details["song_file"] = arg
            elif opt in ('-s', "--sfile"):
                self.details["subtitles"] = arg
                if str(arg).split('.')[1] != "srt":
                    print("Supplied subtitle file needs to be a .srt")
                    sys.exit()
            elif opt in ('-y', "--yfile"):
                self.details["url"] = arg

        # We need to decide which song file we are using
        if "url" in self.details:
            print("Downloading YouTube song...")
            # Set-up the various youtube-dl options, we are using mp3 here because its easier to handle from m4a
            # if mp3 not available, converted with ffmpeg by youtube-dl api
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': 'temp.mp3',
                'writesubtitles': True,
            }
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                # Delete all of the previous files to be safe
                for file in glob.glob('temp.mp3.*.vtt'):
                    os.remove(file)
                # Download from youtube the song file and the subtitles
                result = ydl.download([self.details["url"]])
                self.details["song_file"] = "temp.mp3"
                self.details["subtitles"] = "temp.mp3.en.vtt"



        # Get the total song length
        metadata = utils.mediainfo(self.details["song_file"])
        # args = ("ffprobe", "-show_entries", "format=duration", "-i", self.details["song_file"])
        # # Launch the ffprobe subprocess
        # popen = subprocess.Popen(args, stdout=subprocess.PIPE)
        # popen.wait()
        # # Do a basic regex to find the song length, should be the first value
        # song_length = re.findall(r'\d*\.?\d*', popen.stdout.read().decode("utf-8"))

        self.calculateTempo()

        # Store the current song length
        self.details["song_length"] = int(float(metadata["duration"]))
        self.details["artist"] = metadata["TAG"]["artist"] if "artist" in metadata["TAG"] else ""
        self.details["album"] = metadata["TAG"]["album"] if "album" in metadata["TAG"] else ""
        self.details["title"] = metadata["TAG"]["title"] if "title" in metadata["TAG"] else ""
        self.details["sample_rate"] = int(metadata["sample_rate"]) if "sample_rate" in metadata["TAG"] else ""
        self.verify_setup()

    def calculateTempo(self):
        model_name = 'cnn'
        classifier = TempoClassifier(model_name)
        features = read_features(self.details["song_file"])
        tempo = classifier.estimate_tempo(features, interpolate=False)
        self.details["bpm"] = tempo

    def verify_setup(self):
        # It is possible that we have not correctly set-up the various functions, this function solves the issue
        if not os.path.isdir('output/'):
            print("Output directory not found! Creating output directory")
            os.mkdir('output')
        if not os.path.isdir('pretrained_models'):
            print("AutoKaraoke needs to download Spleeter models. This may take a few minutes.")

    def isolate_vocals(self):
        # Uses Spleeter to split vocals and instrumentals (https://github.com/deezer/spleeter)
        print("Isolating vocals from instrumentals.")
        separator = Separator('spleeter:2stems')
        # Use cached pitch isolation if possible
        if not os.path.isdir("output/" + os.path.splitext(self.details["song_file"])[0]):
            separator.separate_to_file(self.details["song_file"], "output/")
        else:
            print("Loading vocals from cache")

        return self.details["song_file"]

    def generate_pitch_values(self):
        # Estimate pitch using Crepe (https://pypi.org/project/crepe/)
        print("Estimating pitch values. This will take some time based on the power of your CPU!\n"
              "Using GPU tensorflow will lead to better performance: https://www.tensorflow.org/install/gpu ")
        # Generate the paths for the file
        # crepe_cmd = "crepe output/" + os.path.splitext(self.details["song_file"])[0] + "/vocals.wav"
        # Calls the crepe subprocess
        # os.system(crepe_cmd)

        # audio, sr = a2n.audio_from_file("output/" + os.path.splitext(self.details["song_file"])[0] + "/vocals.wav")
        # time, frequency, confidence, activation = crepe.predict(audio, sr, viterbi=True)
        if not os.path.exists("output/" + os.path.splitext(self.details["song_file"])[0] + "/vocals.f0.csv"):
            crepe.process_file("output/" + os.path.splitext(self.details["song_file"])[0] + "/vocals.wav", "output/" + os.path.splitext(self.details["song_file"])[0])
        else:
            print("Loading pitch values from cache")
        # All heavy data processing has been completed, let us load in the results
        csv_loc = "output/" + os.path.splitext(self.details["song_file"])[0] + "/vocals.f0.csv"

        return csv_loc

    def generateFreqEMA(self, pitch_vocals):
        freqs = pd.read_csv(pitch_vocals).frequency
        freqs_ema = freqs.ewm(halflife=30).mean()

        # Generate beat wise sample
        beats_per_second = self.details["bpm"] / 60
        totalBeats = beats_per_second * self.details["song_length"]
        sample_period = int((1000 / beats_per_second) / 10)
        # sample_period = int(len(freqs_ema) / totalBeats)
        # Have a list of the actual frequency samples in order based on the BPM of the song
        freq_list = []
        for i in range(int(totalBeats)):
            freq_list.append(freqs_ema[i * sample_period])
        return freq_list

    def generateLexemes(self, ema_freq):
        beats_per_second = self.details["bpm"] / 60
        totalBeats = beats_per_second * self.details["song_length"]

        # We need a method to find the various timestamps from the file and to convert these timestamps into usable
        # lexemes from which we can map a frequency to using an EMA. Ideally we would have a model that has a good
        # accuracy for determining what each syllable is but this is v. hard and open research problem.
        vocal_filename = "output/" + os.path.splitext(self.details["song_file"])[0] + "/vocals.wav"
        song_file = AudioSegment.from_file(vocal_filename)
        # audio_chunks = split_on_silence(song_file,
        #                                 min_silence_len=100, # Adjust for the type
        #                                 silence_thresh=-20   # Quieter than -16dbFS
        #                                 )
        print("Normalising vocals")
        normalized_sound = effects.normalize(song_file)

        print("Detecting lexemes...")
        nonsilent_data = detect_nonsilent(normalized_sound, min_silence_len=100, silence_thresh=-25, seek_step=1)
        epsilon = (1000 / beats_per_second) / 2
        beats_played = [False for _ in range(int(totalBeats))]
        for chunks in nonsilent_data:
            chunk = [chunk for chunk in chunks]
            # First we find the beat to begin inserting the values into
            startBeat = int((chunk[0] / 1000) * beats_per_second)
            currentMaxBeat = startBeat
            while (currentMaxBeat / beats_per_second) * 1000 < chunk[1]:
                beats_played[currentMaxBeat] = True
                currentMaxBeat = currentMaxBeat + 1

        freqTable = ultrastarUtils.generateFrequencyTable(261.6256, 1000)

        # Convert the binary beats to be a actual song

        # First we get the ultrastar note values for each of the frequenceis
        ultraStarNotes = []
        for index in range(len(beats_played)):
            ultraStarNotes.append((beats_played[index], ultrastarUtils.getUltrastarNote(freqTable, ema_freq[index])))
        return ultraStarNotes

    def generateUltrastarFromJSON(self, json_song):
        # Ultrastar maps have the following format.
        # For simplicity, this script does not concern itself with the types of ultrastar notes (gold ect)
        # and will simply just output a note.
        #
        # The format is the following:
        #   Notes beginning with '-' are linebreaks. These are used to seperate the lines of a song.
        #   Notes beginning with ':' are regular notes, this is all we will output.
        #   The second column number is the number of beats into the song that the note appears (our case the index)
        #   Third column is number of beats that a note is played for
        #   Fourth column is the frequency of the note
        #   Fifth column is the text to be sung
        song = json.loads(json_song)
        # Delete any pre-existing file
        output_file = open(f"{self.details['song_file']}_output.txt", 'w')

        # Handle the creation of Ultrastar metadata (totally done right)
        print(f"#TITLE:{self.details['title']}", file=output_file)
        print(f"#ARTIST:{self.details['artist']}", file=output_file)
        print(f"#MP3:{self.details['song_file']}", file=output_file)
        print(f"#GAP:0", file=output_file) # Needs to be manually entered atm
        print(f"#BPM:{self.details['bpm'] *4}", file=output_file)
        for idx, beat in enumerate(song):
            if beat:
                if beat["played"]:
                    print(f": {idx*3} {beat['length']*3} {beat['frequency']} A", file=output_file)


def main(argv):
    # Load in the songfile and subtitles to check they were valid

    # TODO - Fill in the remainder of the details about the song automatically
    song = UltrastarSong(argv)
    song.isolate_vocals()
    pitch_vocals = song.generate_pitch_values()
    ema_freq = song.generateFreqEMA(pitch_vocals)
    ultraStarNotes = song.generateLexemes(ema_freq)

    # Detect speech from the audio and match with the lyrics provided
    import speech_recognition as sr
    r = sr.Recognizer()

    # Handling line breaks providing that we have supplied a valid vtt file:
    if song.details["subtitles"] != "":
        # For every one of the beats we will 'attempt' to match up a valid sequence of text lyrics from the subtitle file
        # It should be noted random noise may be present so we will establish an acceptable error rate for a sequence of
        # concurrent lyrics based on the syllable count
        subtitle_file = pysrt.open(song.details["subtitles"])
        for line in subtitle_file:
            print(f"{line.start.to_time()} {line.end.to_time()}")


    song_data = [{} for _ in range(len(ultraStarNotes))]
    index = 0
    while index < len(ultraStarNotes):
        should_play, freq = ultraStarNotes[index]
        # If the beat is not silent
        if should_play is True:
            current_freq = freq
            note_length = 1
            while note_length + index < len(ultraStarNotes):
                freq_next = ultraStarNotes[index + note_length]
                if freq_next[0] and freq_next[1] == current_freq:
                    note_length = note_length + 1
                else:
                    break
            song_data[index] = {"length": note_length,
                                "played": True,
                                "frequency": current_freq
                                }
            index = index + note_length
        else:
            song_data[index] = {"length": 0,
                                "played": False,
                                "frequency": 0
                                }
            index = index + 1
    json_song = json.dumps(song_data)
    with open('static/data/song_data.json', 'w') as f:
        json.dump(json_song, f)
    song.generateUltrastarFromJSON(json_song)

    # for i, chunk in enumerate(audio_chunks):
    #     out_file = "splitAudio/chunk{0}.wav".format(i)
    #     chunk.export(out_file, format="wav")


if __name__ == "__main__":
    main(sys.argv[1:])
