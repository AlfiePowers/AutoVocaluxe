# Functions to assist
def generateFrequencyTable(lowest_freq, max_freq):
    # We build a table of frequencies to Ultrastar

    current_freq = lowest_freq
    frequencies = list()
    n = 1
    # Notes within music are harmonic based upon a formulae -> (Middle C) * (2^(n/12)) where n is the step
    # (7 white notes plus 5 black on standard piano) -> 12 -> Gives us an octave scale
    # By using this we can calculate rougly what the current note should be for each frequency.
    frequencies.append(lowest_freq)
    while (current_freq < max_freq):
        current_freq = lowest_freq * pow(2, n / 12)
        frequencies.append(current_freq)
        n += 1
    return frequencies

def getUltrastarNote(table, freq_val):
    note = 0
    for index in range(len(table)-1):
        if freq_val < table[index+1]:
            break
        note = note + 1
    return note

def match_target_amplitude(sound, target_dBFS):
    change_in_dBFS = target_dBFS - sound.dBFS
    return sound.apply_gain(change_in_dBFS)