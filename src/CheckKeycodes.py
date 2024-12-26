import json
import time
from xml.etree.ElementTree import parse

from .lib.Actions import setGameWindowActive
from .lib.EDKeys import EDKeys
from .lib.directinput import PressAndReleaseKey, SCANCODE

def get_key_assignment(latest_bindings, action: str):
    bindings_tree = parse(latest_bindings)
    bindings_root = bindings_tree.getroot()

    for item in bindings_root:
        if item.tag == action:
            return item[0].attrib['Key']

if __name__ == '__main__':
    keyReader = EDKeys("C:\\Users\\treme\\AppData\\Local\\Frontier Developments\\Elite Dangerous")
    keymap = json.load(open('./keymap.json', 'r'))
    # game keybind option is selected in game
    input('press any key to start')
    time.sleep(1)
    setGameWindowActive()
    # loop
    for x in range(0x02, 0xFF):
        if x in keymap.values():
            print("keeping", x)
            continue
        setGameWindowActive()
        ## RESET Loop
        PressAndReleaseKey(SCANCODE["DIK_A"])
        PressAndReleaseKey(SCANCODE["DIK_SPACE"])
        PressAndReleaseKey(SCANCODE["DIK_S"])
        PressAndReleaseKey(SCANCODE["DIK_S"])
        PressAndReleaseKey(SCANCODE["DIK_SPACE"])
        PressAndReleaseKey(SCANCODE["DIK_S"])

        # press ui select to start binding
        PressAndReleaseKey(SCANCODE["DIK_SPACE"])
        time.sleep(0.2)
        # press some dir_x keycode
        PressAndReleaseKey(x)
        time.sleep(0.2)

        # read the existing key so we can make sure to set it to something new
        bindings = keyReader.get_latest_keybinds()
        keyname = get_key_assignment(bindings, "GalaxyMapOpen_Humanoid")
        # Press a key different from the one currently set to force a change in the binding
        PressAndReleaseKey(SCANCODE["DIK_D"] if keyname != "Key_D" else SCANCODE["DIK_A"])

        # save the bindings
        # ESC (Really leave without save)
        PressAndReleaseKey(SCANCODE["DIK_ESCAPE"])
        # select (for cancel)
        PressAndReleaseKey(SCANCODE["DIK_SPACE"])
        # right (move to apply)
        PressAndReleaseKey(SCANCODE["DIK_D"])
        # select (for apply)
        PressAndReleaseKey(SCANCODE["DIK_SPACE"])

        time.sleep(1)

        # read the binding name from file
        bindings = keyReader.get_latest_keybinds()
        print(bindings)
        #input('press any key to continue')
        keyname = get_key_assignment(bindings, "GalaxyMapOpen_Humanoid")
        if keyname in keymap:
            print("??_"+str(x), x)
            keymap["??_"+str(x)] = x
        elif keyname.strip() == '':
            raise Exception('Unknown behaviour')
        else:
            print(keyname, x)
            keymap[keyname] = x
        #input('press any key to continue')
        # save mapping to file
        json.dump(keymap, open('./keymap.json', 'w'))
    # loopend