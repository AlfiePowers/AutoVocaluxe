# Auto karaoke creation software for Vocaluxe
# This has multiple dependencies - Refer to requirements.txt to verify they are installed
import subprocess
import sys, os, getopt, csv, math, re

song_file = ""
subtitles = ""
version = 1.0
bpm = 100
lowest_freq = 32.7032 # This is Peddle C (C1)

def getPitchIndex(beatIndex, bpm):
    return math.floor(beatIndex * 100 * (60 / bpm))

def createUltrastarMap(pitch, song_length):
    # Heading infomation
    print("Generating UltraStar map file - We need some extra info!")
    ema_pitch = []
    ema_pitch.append(float(pitch[0]))
    alpha = 0.2
    index = 1
    for p in pitch:
        if len(ema_pitch) < len(pitch):
            ema_pitch.append(float(pitch[index]) * alpha + (1-alpha) * ema_pitch[index-1])
            index+=1
        else:
            break

    totalBeats = math.floor((song_length * bpm)/60)

    # We build a table of frequencies to Ultrastar
    max_freq = max(ema_pitch)

    frequencies = list()
    current_freq = lowest_freq
    n = 1
    while(current_freq < max_freq):
        current_freq = lowest_freq * pow(2, n/12)
        frequencies.append(current_freq)
        n += 1


    for i in range(0,totalBeats,1):
        index = getPitchIndex(i, bpm)







def main(argv):
    # Handle program arguments
    try:
        opts, args = getopt.getopt(argv, "hi:s", ["ifile=", "sfile="])
    except getopt.GetoptError:
        print("createKaraoke.py -i <inputSongFile> -s <subtitleFile>")
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print("createKaraoke.py -i <inputSongFile> -s <subtitleFile>")
            sys.exit()
        elif opt in ('-i', "--ifile"):
            song_file = arg
        elif opt in ('-s', "--sfile"):
            subtitles = arg
    # Load in the songfile and subtitles to check they were valid

    # Get the total song length
    args = ("ffprobe", "-show_entries", "format=duration", "-i", song_file)
    popen = subprocess.Popen(args, stdout=subprocess.PIPE)
    popen.wait()
    song_length = re.findall(r'\d*\.?\d*', popen.stdout.read().decode("utf-8"))
    song_length = float(list(filter(None, song_length))[0])


    # TODO

    # Song and subtitle files should be loaded, we can continue with the program

    print("AutoKaraoke mapper v", version, " by MrPorky")
    # Just some safety checks for our program
    if not os.path.isdir('output/'):
        print("Output directory not found! Creating output directory")
        os.mkdir('output')
    if not os.path.isdir('pretrained_models'):
        print("AutoKaraoke needs to download Spleeter models. This may take a few minutes.")

    print("Isolating vocals from instrumentals.")
    spleeter_cmd = "spleeter separate -i" + song_file + " -p spleeter:2stems -o output"
    #os.system(spleeter_cmd)

    print("Estimating pitch values. This will take some time based on the power of your CPU!\n"
          "Using GPU tensorflow will lead to better performance: https://www.tensorflow.org/install/gpu ")
    s = os.path.splitext(song_file)
    crepe_cmd = "crepe output/" + os.path.splitext(song_file)[0] + "/vocals.wav"
    # os.system(crepe_cmd)

    # All heavy data processing has been completed, let us load in the results
    csv_loc = "output/" + os.path.splitext(song_file)[0] + "/vocals.f0.csv"

    # Output from crepe has 3 columns:
    # Time (10ms intervals), Predicted pitch, Confidence interval
    pitch = []
    pitch_interval = []
    with open(csv_loc) as pitchCSV:
        csv_reader = csv.reader(pitchCSV)
        next(csv_reader, None)
        for row in csv_reader:
            pitch.append(row[1])
            pitch_interval.append(row[2])

    createUltrastarMap(pitch, song_length)


if __name__ == "__main__":
    main(sys.argv[1:])
