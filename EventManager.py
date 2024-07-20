import sys
from dataclasses import dataclass, field
from datetime import datetime
import json
from typing import Dict, List

import openai
from openai.types.chat import ChatCompletionMessage

@dataclass
class Message(ChatCompletionMessage):
    pass

@dataclass
class Event:
    kind: str = 'game'  # 'user', 'assistant', 'tool', 'game'
    timestamp: datetime = datetime.now()
    content: Dict = field(default_factory=dict)

class EventManager:
    def __init__(self):
        self.pending: List[Event] = []
        self.processed: List[Event] = []
        self.is_replying = False

    def add_game_event(self, content: Dict):
        event = Event(kind="game", content=content)
        self.pending.append(event)
        return self._handle_new_event(event)

    def add_conversation_event(self, role: str, content: str):
        event = Event(kind=role, content=content)
        self.pending.append(event)
        return self._handle_new_event(event)

    def _handle_new_event(self, event: Event):
        if not self.is_replying and self.should_reply():
            self.processed += self.pending
            self.pending = []
            self._trigger_reply(event)
            return True
        return False

    def should_reply(self):
        if len(self.pending) == 0:
            return False

        # check if pending contains conversational events
        if any([item.kind == "user" for item in self.pending]):
            return True

        return False

    def reset_is_replying(self):
        self.is_replying = False

    def _trigger_reply(self, event):
        self.is_replying = True
        # Process the reply here
        print('_trigger_reply would have triggered')
        sys.stdout.flush()


class PromptGenerator:
    def full_event_message(self, event: Event):
        return {
            "role": "user",
            "content": "(Got event "+event.content.get("event")+": "+json.dumps(event.content)+")"
        }

    def simple_event_message(self, event: Event):
        return {
            "role": "user",
            "content": "(Got event "+event.content.get("event")+")"
        }

    def conversation_message(self, event: Event):
        return {
            "role": event.kind,
            "content": event.content
        }

    def generate_prompt(self, events: List[Event]):
        # Collect the last 50 conversational pieces
        conversational_pieces: List[openai.types.chat.ChatCompletionMessage] = list()
        for i in range(len(events)):
            if len(conversational_pieces) >= 50:
                break

            event = events[-i]

            if event.kind == 'game':
                if len(conversational_pieces) < 5:
                    conversational_pieces.append(self.full_event_message(event))
                elif len(conversational_pieces) < 20:
                    conversational_pieces.append(self.simple_event_message(event))
                else:
                    pass

            if event.kind == 'user' or event.kind == 'assistant':
                conversational_pieces.append(self.conversation_message(event))

            # TODO tools, etc...

        conversational_pieces.reverse()  # Restore the original order

        return [{"role": "system", "content": "You are Herika."}] + conversational_pieces

# Example usage
if __name__ == "__main__":

    event_manager = EventManager()
    prompt_generator = PromptGenerator()

    conversation = [
        {
            "role": "user",
            "content": "(Commander Rude has received a text message. Details: {\"timestamp\": \"2024-07-18T21:01:27Z\", \"event\": \"ReceiveText\", \"From\": \"$npc_name_decorate:#name=Solarwind;\", \"From_Localised\": \"Solarwind\", \"Message\": \"$Commuter_AuthorityScan05;\", \"Message_Localised\": \"On what grounds are you scanning this vessel, officer?\", \"Channel\": \"npc\"})"
        },
        {
            "content": "Looks like we’ve got a fiery response from Solarwind. They seem miffed about being scanned. Care to respond, or shall we leave them to stew in their indignation while we move on to more profitable ventures?",
            "role": "assistant"
        },
        {
            "role": "user",
            "content": "Don't you think he might be a good bounty target, since he doesn't like to be scanned?"
        },
        {
            "content": "Excellent point, Commander. His irritation might hide something worth our while. Shall I set a course for Solarwind and prepare our weapons, or would you prefer to handle this more delicately?",
            "role": "assistant"
        },
        {
            "role": "user",
            "content": "I think I'll do it more telekly."
        },
        {
            "content": "Stealthy it is. I'll be discreetly monitoring everything. Ready to deploy hardpoints and initiate silent running on your command, Commander. Let's catch Solarwind off-guard.",
            "role": "assistant"
        },
    ]

    events = [
        {"timestamp": "2024-07-18T20:46:13Z", "event": "Fileheader", "part": 1, "language": "English/UK",
         "Odyssey": True, "gameversion": "4.0.0.1807", "build": "r303387/r0 "},
        {"timestamp": "2024-07-18T20:50:29Z", "event": "Commander", "FID": "F9569014", "Name": "TREMENDOUSLYRUDE.TTV"},
        {"timestamp": "2024-07-18T20:50:29Z", "event": "Materials",
         "Raw": [{"Name": "carbon", "Count": 166}, {"Name": "phosphorus", "Count": 179},
                 {"Name": "sulphur", "Count": 167}, {"Name": "iron", "Count": 26}, {"Name": "polonium", "Count": 25},
                 {"Name": "manganese", "Count": 98}, {"Name": "molybdenum", "Count": 30},
                 {"Name": "arsenic", "Count": 78}, {"Name": "nickel", "Count": 276}, {"Name": "vanadium", "Count": 83},
                 {"Name": "mercury", "Count": 30}, {"Name": "ruthenium", "Count": 17},
                 {"Name": "tellurium", "Count": 29}, {"Name": "tungsten", "Count": 32}, {"Name": "zinc", "Count": 40},
                 {"Name": "technetium", "Count": 22}, {"Name": "yttrium", "Count": 24},
                 {"Name": "antimony", "Count": 25}, {"Name": "boron", "Count": 33}, {"Name": "zirconium", "Count": 117},
                 {"Name": "lead", "Count": 300}, {"Name": "rhenium", "Count": 300}, {"Name": "germanium", "Count": 95},
                 {"Name": "tin", "Count": 13}, {"Name": "chromium", "Count": 118}, {"Name": "niobium", "Count": 26},
                 {"Name": "cadmium", "Count": 16}],
         "Manufactured": [{"Name": "conductiveceramics", "Name_Localised": "Conductive Ceramics", "Count": 38},
                          {"Name": "heatdispersionplate", "Name_Localised": "Heat Dispersion Plate", "Count": 51},
                          {"Name": "mechanicalcomponents", "Name_Localised": "Mechanical Components", "Count": 48},
                          {"Name": "chemicalprocessors", "Name_Localised": "Chemical Processors", "Count": 6},
                          {"Name": "conductivecomponents", "Name_Localised": "Conductive Components", "Count": 57},
                          {"Name": "heatexchangers", "Name_Localised": "Heat Exchangers", "Count": 60},
                          {"Name": "shieldemitters", "Name_Localised": "Shield Emitters", "Count": 112},
                          {"Name": "phasealloys", "Name_Localised": "Phase Alloys", "Count": 13},
                          {"Name": "precipitatedalloys", "Name_Localised": "Precipitated Alloys", "Count": 1},
                          {"Name": "focuscrystals", "Name_Localised": "Focus Crystals", "Count": 12},
                          {"Name": "mechanicalequipment", "Name_Localised": "Mechanical Equipment", "Count": 25},
                          {"Name": "heatconductionwiring", "Name_Localised": "Heat Conduction Wiring", "Count": 34},
                          {"Name": "basicconductors", "Name_Localised": "Basic Conductors", "Count": 45},
                          {"Name": "shieldingsensors", "Name_Localised": "Shielding Sensors", "Count": 36},
                          {"Name": "heatvanes", "Name_Localised": "Heat Vanes", "Count": 1},
                          {"Name": "filamentcomposites", "Name_Localised": "Filament Composites", "Count": 27},
                          {"Name": "salvagedalloys", "Name_Localised": "Salvaged Alloys", "Count": 10},
                          {"Name": "configurablecomponents", "Name_Localised": "Configurable Components", "Count": 1},
                          {"Name": "highdensitycomposites", "Name_Localised": "High Density Composites", "Count": 26},
                          {"Name": "refinedfocuscrystals", "Name_Localised": "Refined Focus Crystals", "Count": 2},
                          {"Name": "crystalshards", "Name_Localised": "Crystal Shards", "Count": 72},
                          {"Name": "compoundshielding", "Name_Localised": "Compound Shielding", "Count": 3},
                          {"Name": "conductivepolymers", "Name_Localised": "Conductive Polymers", "Count": 1},
                          {"Name": "wornshieldemitters", "Name_Localised": "Worn Shield Emitters", "Count": 58},
                          {"Name": "uncutfocuscrystals", "Name_Localised": "Flawed Focus Crystals", "Count": 17},
                          {"Name": "mechanicalscrap", "Name_Localised": "Mechanical Scrap", "Count": 28},
                          {"Name": "galvanisingalloys", "Name_Localised": "Galvanising Alloys", "Count": 42},
                          {"Name": "hybridcapacitors", "Name_Localised": "Hybrid Capacitors", "Count": 7},
                          {"Name": "electrochemicalarrays", "Name_Localised": "Electrochemical Arrays", "Count": 1},
                          {"Name": "heatresistantceramics", "Name_Localised": "Heat Resistant Ceramics", "Count": 6},
                          {"Name": "chemicalstorageunits", "Name_Localised": "Chemical Storage Units", "Count": 10},
                          {"Name": "compactcomposites", "Name_Localised": "Compact Composites", "Count": 62},
                          {"Name": "gridresistors", "Name_Localised": "Grid Resistors", "Count": 3},
                          {"Name": "guardian_sentinel_wreckagecomponents",
                           "Name_Localised": "Guardian Wreckage Components", "Count": 47},
                          {"Name": "guardian_powerconduit", "Name_Localised": "Guardian Power Conduit", "Count": 226},
                          {"Name": "guardian_sentinel_weaponparts", "Name_Localised": "Guardian Sentinel Weapon Parts",
                           "Count": 39},
                          {"Name": "guardian_techcomponent", "Name_Localised": "Guardian Technology Component",
                           "Count": 22},
                          {"Name": "guardian_powercell", "Name_Localised": "Guardian Power Cell", "Count": 225},
                          {"Name": "temperedalloys", "Name_Localised": "Tempered Alloys", "Count": 9},
                          {"Name": "unknownenergysource", "Name_Localised": "Sensor Fragment", "Count": 17},
                          {"Name": "tg_wreckagecomponents", "Name_Localised": "Wreckage Components", "Count": 60},
                          {"Name": "tg_biomechanicalconduits", "Name_Localised": "Bio-Mechanical Conduits",
                           "Count": 51}, {"Name": "tg_weaponparts", "Name_Localised": "Weapon Parts", "Count": 36},
                          {"Name": "tg_propulsionelement", "Name_Localised": "Propulsion Elements", "Count": 39}],
         "Encoded": [{"Name": "archivedemissiondata", "Name_Localised": "Irregular Emission Data", "Count": 8},
                     {"Name": "shieldpatternanalysis", "Name_Localised": "Aberrant Shield Pattern Analysis",
                      "Count": 15},
                     {"Name": "scanarchives", "Name_Localised": "Unidentified Scan Archives", "Count": 9},
                     {"Name": "bulkscandata", "Name_Localised": "Anomalous Bulk Scan Data", "Count": 28},
                     {"Name": "shielddensityreports", "Name_Localised": "Untypical Shield Scans", "Count": 5},
                     {"Name": "adaptiveencryptors", "Name_Localised": "Adaptive Encryptors Capture", "Count": 6},
                     {"Name": "encryptionarchives", "Name_Localised": "Atypical Encryption Archives", "Count": 31},
                     {"Name": "consumerfirmware", "Name_Localised": "Modified Consumer Firmware", "Count": 66},
                     {"Name": "industrialfirmware", "Name_Localised": "Cracked Industrial Firmware", "Count": 49},
                     {"Name": "disruptedwakeechoes", "Name_Localised": "Atypical Disrupted Wake Echoes", "Count": 33},
                     {"Name": "wakesolutions", "Name_Localised": "Strange Wake Solutions", "Count": 14},
                     {"Name": "hyperspacetrajectories", "Name_Localised": "Eccentric Hyperspace Trajectories",
                      "Count": 7},
                     {"Name": "legacyfirmware", "Name_Localised": "Specialised Legacy Firmware", "Count": 37},
                     {"Name": "emissiondata", "Name_Localised": "Unexpected Emission Data", "Count": 16},
                     {"Name": "scandatabanks", "Name_Localised": "Classified Scan Databanks", "Count": 2},
                     {"Name": "encryptedfiles", "Name_Localised": "Unusual Encrypted Files", "Count": 21},
                     {"Name": "securityfirmware", "Name_Localised": "Security Firmware Patch", "Count": 4},
                     {"Name": "fsdtelemetry", "Name_Localised": "Anomalous FSD Telemetry", "Count": 15},
                     {"Name": "embeddedfirmware", "Name_Localised": "Modified Embedded Firmware", "Count": 1},
                     {"Name": "shieldsoakanalysis", "Name_Localised": "Inconsistent Shield Soak Analysis", "Count": 13},
                     {"Name": "encryptioncodes", "Name_Localised": "Tagged Encryption Codes", "Count": 21},
                     {"Name": "tg_interdictiondata", "Name_Localised": "Thargoid Interdiction Telemetry", "Count": 108},
                     {"Name": "shieldcyclerecordings", "Name_Localised": "Distorted Shield Cycle Recordings",
                      "Count": 12},
                     {"Name": "ancientculturaldata", "Name_Localised": "Pattern Beta Obelisk Data", "Count": 45},
                     {"Name": "ancientlanguagedata", "Name_Localised": "Pattern Delta Obelisk Data", "Count": 24},
                     {"Name": "ancienthistoricaldata", "Name_Localised": "Pattern Gamma Obelisk Data", "Count": 51},
                     {"Name": "ancientbiologicaldata", "Name_Localised": "Pattern Alpha Obelisk Data", "Count": 42},
                     {"Name": "ancienttechnologicaldata", "Name_Localised": "Pattern Epsilon Obelisk Data", "Count": 7},
                     {"Name": "symmetrickeys", "Name_Localised": "Open Symmetric Keys", "Count": 15},
                     {"Name": "encodedscandata", "Name_Localised": "Divergent Scan Data", "Count": 3},
                     {"Name": "decodedemissiondata", "Name_Localised": "Decoded Emission Data", "Count": 4},
                     {"Name": "scrambledemissiondata", "Name_Localised": "Exceptional Scrambled Emission Data",
                      "Count": 18},
                     {"Name": "guardian_vesselblueprint", "Name_Localised": "Guardian Vessel Blueprint Fragment",
                      "Count": 1},
                     {"Name": "shieldfrequencydata", "Name_Localised": "Peculiar Shield Frequency Data", "Count": 1},
                     {"Name": "tg_shutdowndata", "Name_Localised": "Massive Energy Surge Analytics", "Count": 1}]},
        {"timestamp": "2024-07-18T20:50:29Z", "event": "Rank", "Combat": 5, "Trade": 4, "Explore": 6, "Soldier": 5,
         "Exobiologist": 0, "Empire": 3, "Federation": 5, "CQC": 0},
        {"timestamp": "2024-07-18T20:50:29Z", "event": "Progress", "Combat": 2, "Trade": 46, "Explore": 19,
         "Soldier": 4, "Exobiologist": 7, "Empire": 63, "Federation": 12, "CQC": 0},
        {"timestamp": "2024-07-18T20:50:29Z", "event": "Reputation", "Empire": 75.000000, "Federation": 90.134697,
         "Independent": 0.000000, "Alliance": 0.567000},
        {"timestamp": "2024-07-18T20:50:29Z", "event": "EngineerProgress", "Engineers": [
            {"Engineer": "Hera Tani", "EngineerID": 300090, "Progress": "Unlocked", "RankProgress": 0, "Rank": 5},
            {"Engineer": "Professor Palin", "EngineerID": 300220, "Progress": "Unlocked", "RankProgress": 0, "Rank": 5},
            {"Engineer": "Felicity Farseer", "EngineerID": 300100, "Progress": "Unlocked", "RankProgress": 0,
             "Rank": 5}, {"Engineer": "Eleanor Bresa", "EngineerID": 400011, "Progress": "Known"},
            {"Engineer": "Hero Ferrari", "EngineerID": 400003, "Progress": "Invited"},
            {"Engineer": "Tiana Fortune", "EngineerID": 300270, "Progress": "Invited"},
            {"Engineer": "Jude Navarro", "EngineerID": 400001, "Progress": "Known"},
            {"Engineer": "Broo Tarquin", "EngineerID": 300030, "Progress": "Invited"},
            {"Engineer": "Etienne Dorn", "EngineerID": 300290, "Progress": "Invited"},
            {"Engineer": "Lori Jameson", "EngineerID": 300230, "Progress": "Known"},
            {"Engineer": "Bill Turner", "EngineerID": 300010, "Progress": "Known"},
            {"Engineer": "Liz Ryder", "EngineerID": 300080, "Progress": "Unlocked", "RankProgress": 0, "Rank": 5},
            {"Engineer": "Rosa Dayette", "EngineerID": 400012, "Progress": "Known"},
            {"Engineer": "Juri Ishmaak", "EngineerID": 300250, "Progress": "Unlocked", "RankProgress": 0, "Rank": 1},
            {"Engineer": "Zacariah Nemo", "EngineerID": 300050, "Progress": "Known"},
            {"Engineer": "Mel Brandon", "EngineerID": 300280, "Progress": "Known"},
            {"Engineer": "Selene Jean", "EngineerID": 300210, "Progress": "Unlocked", "RankProgress": 0, "Rank": 5},
            {"Engineer": "Marco Qwent", "EngineerID": 300200, "Progress": "Unlocked", "RankProgress": 0, "Rank": 5},
            {"Engineer": "Chloe Sedesi", "EngineerID": 300300, "Progress": "Invited"},
            {"Engineer": "Baltanos", "EngineerID": 400010, "Progress": "Known"},
            {"Engineer": "Petra Olmanova", "EngineerID": 300130, "Progress": "Invited"},
            {"Engineer": "Ram Tah", "EngineerID": 300110, "Progress": "Unlocked", "RankProgress": 0, "Rank": 1},
            {"Engineer": "The Dweller", "EngineerID": 300180, "Progress": "Unlocked", "RankProgress": 0, "Rank": 5},
            {"Engineer": "Elvira Martuuk", "EngineerID": 300160, "Progress": "Unlocked", "RankProgress": 0, "Rank": 5},
            {"Engineer": "Lei Cheung", "EngineerID": 300120, "Progress": "Unlocked", "RankProgress": 0, "Rank": 5},
            {"Engineer": "Kit Fowler", "EngineerID": 400004, "Progress": "Known"},
            {"Engineer": "Didi Vatermann", "EngineerID": 300000, "Progress": "Unlocked", "RankProgress": 0, "Rank": 5},
            {"Engineer": "Tod 'The Blaster' McQuinn", "EngineerID": 300260, "Progress": "Unlocked", "RankProgress": 0,
             "Rank": 5},
            {"Engineer": "Domino Green", "EngineerID": 400002, "Progress": "Unlocked", "RankProgress": 0, "Rank": 0},
            {"Engineer": "Marsha Hicks", "EngineerID": 300150, "Progress": "Invited"}]},
        {"timestamp": "2024-07-18T20:50:29Z", "event": "SquadronStartup", "SquadronName": "NIGHTFALL NAVY",
         "CurrentRank": 0},
        {"timestamp": "2024-07-18T20:50:29Z", "event": "LoadGame", "FID": "F9569014",
         "Commander": "TREMENDOUSLYRUDE.TTV", "Horizons": True, "Odyssey": True, "Ship": "Empire_Courier",
         "Ship_Localised": "Imperial Courier", "ShipID": 88, "ShipName": "", "ShipIdent": "", "FuelLevel": 11.590000,
         "FuelCapacity": 12.000000, "GameMode": "Solo", "Credits": 106846300, "Loan": 0, "language": "English/UK",
         "gameversion": "4.0.0.1807", "build": "r303387/r0 "},
        {"timestamp": "2024-07-18T20:50:33Z", "event": "Statistics",
         "Bank_Account": {"Current_Wealth": 923347832, "Spent_On_Ships": 360777103, "Spent_On_Outfitting": 910538042,
                          "Spent_On_Repairs": 23807110, "Spent_On_Fuel": 276772, "Spent_On_Ammo_Consumables": 2114747,
                          "Insurance_Claims": 19, "Spent_On_Insurance": 160225577, "Owned_Ship_Count": 8,
                          "Spent_On_Suits": 34050000, "Spent_On_Weapons": 37350000,
                          "Spent_On_Suit_Consumables": 3478000, "Suits_Owned": 7, "Weapons_Owned": 12,
                          "Spent_On_Premium_Stock": 63875000, "Premium_Stock_Bought": 24},
         "Combat": {"Bounties_Claimed": 45, "Bounty_Hunting_Profit": 2511835, "Combat_Bonds": 520,
                    "Combat_Bond_Profits": 162252387, "Assassinations": 8, "Assassination_Profits": 2253177,
                    "Highest_Single_Reward": 690550, "Skimmers_Killed": 11, "OnFoot_Combat_Bonds": 2399,
                    "OnFoot_Combat_Bonds_Profits": 271733335, "OnFoot_Vehicles_Destroyed": 0,
                    "OnFoot_Ships_Destroyed": 1, "Dropships_Taken": 14, "Dropships_Booked": 37,
                    "Dropships_Cancelled": 8, "ConflictZone_High": 108, "ConflictZone_Medium": 4,
                    "ConflictZone_Low": 55, "ConflictZone_Total": 167, "ConflictZone_High_Wins": 106,
                    "ConflictZone_Medium_Wins": 4, "ConflictZone_Low_Wins": 53, "ConflictZone_Total_Wins": 163,
                    "Settlement_Defended": 11, "Settlement_Conquered": 1, "OnFoot_Skimmers_Killed": 19,
                    "OnFoot_Scavs_Killed": 44},
         "Crime": {"Notoriety": 0, "Fines": 112, "Total_Fines": 19825, "Bounties_Received": 188,
                   "Total_Bounties": 186200, "Highest_Bounty": 1000, "Malware_Uploaded": 0,
                   "Settlements_State_Shutdown": 6, "Production_Sabotage": 2, "Production_Theft": 7,
                   "Total_Murders": 627, "Citizens_Murdered": 231, "Omnipol_Murdered": 82, "Guards_Murdered": 314,
                   "Data_Stolen": 151, "Goods_Stolen": 1552, "Sample_Stolen": 4, "Total_Stolen": 1707,
                   "Turrets_Destroyed": 6, "Turrets_Overloaded": 0, "Turrets_Total": 6,
                   "Value_Stolen_StateChange": 860000, "Profiles_Cloned": 61},
         "Smuggling": {"Black_Markets_Traded_With": 0, "Black_Markets_Profits": 0, "Resources_Smuggled": 0,
                       "Average_Profit": 0, "Highest_Single_Transaction": 0},
         "Trading": {"Markets_Traded_With": 9, "Market_Profits": 12327789, "Resources_Traded": 635,
                     "Average_Profit": 648831, "Highest_Single_Transaction": 6890208, "Data_Sold": 3, "Goods_Sold": 666,
                     "Assets_Sold": 0},
         "Mining": {"Mining_Profits": 5720090, "Quantity_Mined": 110, "Materials_Collected": 5582},
         "Exploration": {"Systems_Visited": 2135, "Exploration_Profits": 50239913, "Planets_Scanned_To_Level_2": 3614,
                         "Planets_Scanned_To_Level_3": 3614, "Efficient_Scans": 3, "Highest_Payout": 2998275,
                         "Total_Hyperspace_Distance": 88961, "Total_Hyperspace_Jumps": 2588,
                         "Greatest_Distance_From_Start": 5392.8408197741, "Time_Played": 3227100,
                         "OnFoot_Distance_Travelled": 320726, "Shuttle_Journeys": 160,
                         "Shuttle_Distance_Travelled": 5773.4315686035, "Spent_On_Shuttles": 2686639,
                         "First_Footfalls": 0, "Planet_Footfalls": 80, "Settlements_Visited": 21},
         "Passengers": {"Passengers_Missions_Accepted": 128, "Passengers_Missions_Bulk": 6224,
                        "Passengers_Missions_VIP": 0, "Passengers_Missions_Delivered": 6224,
                        "Passengers_Missions_Ejected": 0},
         "Search_And_Rescue": {"SearchRescue_Traded": 6, "SearchRescue_Profit": 120567, "SearchRescue_Count": 2,
                               "Salvage_Legal_POI": 3673900, "Salvage_Legal_Settlements": 418100,
                               "Salvage_Illegal_POI": 3025000, "Salvage_Illegal_Settlements": 0, "Maglocks_Opened": 216,
                               "Panels_Opened": 99, "Settlements_State_FireOut": 8, "Settlements_State_Reboot": 2},
         "TG_ENCOUNTERS": {"TG_ENCOUNTER_KILLED": 211, "TG_ENCOUNTER_TOTAL": 39,
                           "TG_ENCOUNTER_TOTAL_LAST_SYSTEM": "Asterope",
                           "TG_ENCOUNTER_TOTAL_LAST_TIMESTAMP": "3310-07-11 22:14",
                           "TG_ENCOUNTER_TOTAL_LAST_SHIP": "Adder"},
         "Crafting": {"Count_Of_Used_Engineers": 11, "Recipes_Generated": 844, "Recipes_Generated_Rank_1": 196,
                      "Recipes_Generated_Rank_2": 169, "Recipes_Generated_Rank_3": 213, "Recipes_Generated_Rank_4": 148,
                      "Recipes_Generated_Rank_5": 118, "Suit_Mods_Applied": 0, "Weapon_Mods_Applied": 1,
                      "Suits_Upgraded": 0, "Weapons_Upgraded": 3, "Suits_Upgraded_Full": 0, "Weapons_Upgraded_Full": 0,
                      "Suit_Mods_Applied_Full": 0, "Weapon_Mods_Applied_Full": 0},
         "Crew": {"NpcCrew_TotalWages": 28201607, "NpcCrew_Hired": 5, "NpcCrew_Fired": 4, "NpcCrew_Died": 4},
         "Multicrew": {"Multicrew_Time_Total": 308709, "Multicrew_Gunner_Time_Total": 0,
                       "Multicrew_Fighter_Time_Total": 0, "Multicrew_Credits_Total": 0, "Multicrew_Fines_Total": 0},
         "Material_Trader_Stats": {"Trades_Completed": 170, "Materials_Traded": 8265, "Encoded_Materials_Traded": 1154,
                                   "Raw_Materials_Traded": 5973, "Grade_1_Materials_Traded": 2223,
                                   "Grade_2_Materials_Traded": 2303, "Grade_3_Materials_Traded": 2034,
                                   "Grade_4_Materials_Traded": 1205, "Grade_5_Materials_Traded": 500,
                                   "Assets_Traded_In": 129, "Assets_Traded_Out": 365},
         "Exobiology": {"Organic_Genus_Encountered": 4, "Organic_Species_Encountered": 4,
                        "Organic_Variant_Encountered": 1, "Organic_Data_Profits": 1658500, "Organic_Data": 1,
                        "First_Logged_Profits": 0, "First_Logged": 0, "Organic_Systems": 1, "Organic_Planets": 1,
                        "Organic_Genus": 1, "Organic_Species": 1}},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "ReceiveText", "From": "",
         "Message": "$COMMS_entered:#name=Sol;", "Message_Localised": "Entered Channel: Sol", "Channel": "npc"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "$MULTIPLAYER_SCENARIO77_TITLE;", "SignalName_Localised": "Resource Extraction Site [Low]",
         "SignalType": "ResourceExtraction"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "$MULTIPLAYER_SCENARIO77_TITLE;", "SignalName_Localised": "Resource Extraction Site [Low]",
         "SignalType": "ResourceExtraction"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "FCI Information", "SignalType": "TouristBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Columbus", "SignalType": "StationBernalSphere", "IsStation": True},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "$MULTIPLAYER_SCENARIO78_TITLE;", "SignalName_Localised": "Resource Extraction Site [High]",
         "SignalType": "ResourceExtraction"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "$NumberStation:#index=1;", "SignalName_Localised": "Unregistered Comms Beacon",
         "SignalType": "Generic"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Europa Ice Geyser", "SignalType": "TouristBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Delphi Control Chapter", "SignalType": "Installation"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "SOL-044 Aquarius-class Tanker", "SignalType": "Megaship"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "$NumberStation:#index=1;", "SignalName_Localised": "Unregistered Comms Beacon",
         "SignalType": "Generic"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Galileo", "SignalType": "StationBernalSphere", "IsStation": True},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Congressional Streamlining", "SignalType": "TouristBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "M.Gorbachev", "SignalType": "StationONeilOrbis", "IsStation": True},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Abraham Lincoln", "SignalType": "StationONeilOrbis", "IsStation": True},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Li Qing Jao", "SignalType": "StationONeilCylinder", "IsStation": True},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Pilots' Memorial", "SignalType": "Generic"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Interplanetary Road Trip", "SignalType": "TouristBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Ancient History", "SignalType": "TouristBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "New Leadership", "SignalType": "TouristBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "$FIXED_EVENT_CAPSHIP;", "SignalName_Localised": "CAPITAL SHIP", "SignalType": "Generic"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Cradle of Humanity", "SignalType": "TouristBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Titan City", "SignalType": "StationONeilOrbis", "IsStation": True},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "$MULTIPLAYER_SCENARIO77_TITLE;", "SignalName_Localised": "Resource Extraction Site [Low]",
         "SignalType": "ResourceExtraction"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "$MULTIPLAYER_SCENARIO14_TITLE;", "SignalName_Localised": "Resource Extraction Site",
         "SignalType": "ResourceExtraction"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "$MULTIPLAYER_SCENARIO14_TITLE;", "SignalName_Localised": "Resource Extraction Site",
         "SignalType": "ResourceExtraction"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "FIA Responsibilities", "SignalType": "TouristBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Second Terraforming Attempt", "SignalType": "TouristBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Mars High", "SignalType": "StationONeilOrbis", "IsStation": True},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Federal Constitution", "SignalType": "TouristBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "SOL-937 Sagan-class Traveller", "SignalType": "Megaship"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Nonhuman Relic", "SignalType": "TouristBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Tyrell Biggs' Election", "SignalType": "TouristBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Relocation", "SignalType": "TouristBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Federal Congress", "SignalType": "TouristBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Halsey Shares Her Vision", "SignalType": "TouristBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "$FIXED_EVENT_CAPSHIP;", "SignalName_Localised": "CAPITAL SHIP", "SignalType": "Generic"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "$MULTIPLAYER_SCENARIO42_TITLE;", "SignalName_Localised": "Nav Beacon",
         "SignalType": "NavBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Notable Presidents", "SignalType": "TouristBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Conjoint Mathematic Services", "SignalType": "Installation"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "$MULTIPLAYER_SCENARIO77_TITLE;", "SignalName_Localised": "Resource Extraction Site [Low]",
         "SignalType": "ResourceExtraction"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "$MULTIPLAYER_SCENARIO77_TITLE;", "SignalName_Localised": "Resource Extraction Site [Low]",
         "SignalType": "ResourceExtraction"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Daedalus", "SignalType": "StationONeilOrbis", "IsStation": True},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "The Birthright Wars", "SignalType": "TouristBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Chamberlain Foundation", "SignalType": "Installation"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Gellan Scandal", "SignalType": "TouristBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Burnell Station", "SignalType": "Outpost"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Primary Transport Authority", "SignalType": "Installation"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "FSSSignalDiscovered", "SystemAddress": 10477373803,
         "SignalName": "Actaea Ice Fumarole", "SignalType": "TouristBeacon"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "Location", "DistFromStarLS": 494.073001, "Docked": True,
         "StationName": "Galileo", "StationType": "Bernal", "MarketID": 128016640,
         "StationFaction": {"Name": "Mother Gaia"}, "StationGovernment": "$government_Democracy;",
         "StationGovernment_Localised": "Democracy", "StationAllegiance": "Federation",
         "StationServices": ["dock", "autodock", "blackmarket", "commodities", "contacts", "exploration", "missions",
                             "outfitting", "crewlounge", "rearm", "refuel", "repair", "shipyard", "tuning", "engineer",
                             "missionsgenerated", "flightcontroller", "stationoperations", "powerplay", "searchrescue",
                             "stationMenu", "shop", "livery", "socialspace", "bartender", "vistagenomics",
                             "pioneersupplies", "apexinterstellar", "frontlinesolutions"],
         "StationEconomy": "$economy_Refinery;", "StationEconomy_Localised": "Refinery",
         "StationEconomies": [{"Name": "$economy_Refinery;", "Name_Localised": "Refinery", "Proportion": 1.000000}],
         "Taxi": False, "Multicrew": False, "StarSystem": "Sol", "SystemAddress": 10477373803,
         "StarPos": [0.00000, 0.00000, 0.00000], "SystemAllegiance": "Federation",
         "SystemEconomy": "$economy_Refinery;", "SystemEconomy_Localised": "Refinery",
         "SystemSecondEconomy": "$economy_Service;", "SystemSecondEconomy_Localised": "Service",
         "SystemGovernment": "$government_Democracy;", "SystemGovernment_Localised": "Democracy",
         "SystemSecurity": "$SYSTEM_SECURITY_high;", "SystemSecurity_Localised": "High Security",
         "Population": 22780919531, "Body": "Galileo", "BodyID": 52, "BodyType": "Station", "Factions": [
            {"Name": "Federal Congress", "FactionState": "None", "Government": "Democracy", "Influence": 0.145000,
             "Allegiance": "Federation", "Happiness": "$Faction_HappinessBand2;", "Happiness_Localised": "Happy",
             "MyReputation": 0.000000},
            {"Name": "Sol Workers' Party", "FactionState": "None", "Government": "Democracy", "Influence": 0.202000,
             "Allegiance": "Federation", "Happiness": "$Faction_HappinessBand2;", "Happiness_Localised": "Happy",
             "MyReputation": 0.000000},
            {"Name": "Sol Constitution Party", "FactionState": "None", "Government": "Democracy", "Influence": 0.137000,
             "Allegiance": "Federation", "Happiness": "$Faction_HappinessBand2;", "Happiness_Localised": "Happy",
             "MyReputation": 0.000000},
            {"Name": "Mother Gaia", "FactionState": "None", "Government": "Democracy", "Influence": 0.345000,
             "Allegiance": "Federation", "Happiness": "$Faction_HappinessBand2;", "Happiness_Localised": "Happy",
             "MyReputation": 14.976200},
            {"Name": "Sol Nationalists", "FactionState": "None", "Government": "Democracy", "Influence": 0.161000,
             "Allegiance": "Federation", "Happiness": "$Faction_HappinessBand2;", "Happiness_Localised": "Happy",
             "MyReputation": 0.000000, "RecoveringStates": [{"State": "PublicHoliday", "Trend": 0}]},
            {"Name": "Aegis Core", "FactionState": "None", "Government": "Cooperative", "Influence": 0.010000,
             "Allegiance": "Independent", "Happiness": "$Faction_HappinessBand2;", "Happiness_Localised": "Happy",
             "MyReputation": 0.000000}], "SystemFaction": {"Name": "Mother Gaia"}},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "Music", "MusicTrack": "NoTrack"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "ShipLocker", "Items": [
            {"Name": "weaponschematic", "Name_Localised": "Weapon Schematic", "OwnerID": 0, "MissionID": 889869579,
             "Count": 1}, {"Name": "chemicalprocesssample", "Name_Localised": "Chemical Process Sample", "OwnerID": 0,
                           "MissionID": 891285623, "Count": 1},
            {"Name": "insightdatabank", "Name_Localised": "Insight Data Bank", "OwnerID": 0, "MissionID": 967321061,
             "Count": 1}, {"Name": "chemicalsample", "Name_Localised": "Chemical Sample", "OwnerID": 0, "Count": 4},
            {"Name": "geneticsample", "Name_Localised": "Biological Sample", "OwnerID": 0, "Count": 5},
            {"Name": "gmeds", "Name_Localised": "G-Meds", "OwnerID": 0, "Count": 14},
            {"Name": "healthmonitor", "Name_Localised": "Health Monitor", "OwnerID": 0, "Count": 9},
            {"Name": "inertiacanister", "Name_Localised": "Inertia Canister", "OwnerID": 0, "Count": 2},
            {"Name": "insight", "OwnerID": 0, "Count": 11},
            {"Name": "insightdatabank", "Name_Localised": "Insight Data Bank", "OwnerID": 0, "Count": 3},
            {"Name": "personalcomputer", "Name_Localised": "Personal Computer", "OwnerID": 0, "Count": 13},
            {"Name": "syntheticgenome", "Name_Localised": "Synthetic Genome", "OwnerID": 0, "Count": 4},
            {"Name": "geneticrepairmeds", "Name_Localised": "Genetic Repair Meds", "OwnerID": 0, "Count": 3},
            {"Name": "buildingschematic", "Name_Localised": "Building Schematic", "OwnerID": 0, "Count": 8},
            {"Name": "compactlibrary", "Name_Localised": "Compact Library", "OwnerID": 0, "Count": 11},
            {"Name": "hush", "OwnerID": 0, "Count": 6}, {"Name": "infinity", "OwnerID": 0, "Count": 7},
            {"Name": "insightentertainmentsuite", "Name_Localised": "Insight Entertainment Suite", "OwnerID": 0,
             "Count": 13}, {"Name": "lazarus", "OwnerID": 0, "Count": 4},
            {"Name": "microbialinhibitor", "Name_Localised": "Microbial Inhibitor", "OwnerID": 0, "Count": 3},
            {"Name": "nutritionalconcentrate", "Name_Localised": "Nutritional Concentrate", "OwnerID": 0, "Count": 9},
            {"Name": "personaldocuments", "Name_Localised": "Personal Documents", "OwnerID": 0, "Count": 2},
            {"Name": "push", "OwnerID": 0, "Count": 5},
            {"Name": "suitschematic", "Name_Localised": "Suit Schematic", "OwnerID": 0, "Count": 7},
            {"Name": "surveillanceequipment", "Name_Localised": "Surveillance Equipment", "OwnerID": 0, "Count": 3},
            {"Name": "universaltranslator", "Name_Localised": "Universal Translator", "OwnerID": 0, "Count": 4},
            {"Name": "weaponschematic", "Name_Localised": "Weapon Schematic", "OwnerID": 7622509, "Count": 1},
            {"Name": "weaponschematic", "Name_Localised": "Weapon Schematic", "OwnerID": 0, "Count": 6},
            {"Name": "agriculturalprocesssample", "Name_Localised": "Agricultural Process Sample", "OwnerID": 0,
             "Count": 1},
            {"Name": "refinementprocesssample", "Name_Localised": "Refinement Process Sample", "OwnerID": 0,
             "Count": 1},
            {"Name": "compressionliquefiedgas", "Name_Localised": "Compression-Liquefied Gas", "OwnerID": 0,
             "Count": 8},
            {"Name": "degradedpowerregulator", "Name_Localised": "Degraded Power Regulator", "OwnerID": 0, "Count": 6}],
         "Components": [{"Name": "graphene", "OwnerID": 0, "Count": 23}, {"Name": "aerogel", "OwnerID": 0, "Count": 5},
                        {"Name": "carbonfibreplating", "Name_Localised": "Carbon Fibre Plating", "OwnerID": 0,
                         "Count": 6},
                        {"Name": "chemicalcatalyst", "Name_Localised": "Chemical Catalyst", "OwnerID": 0, "Count": 3},
                        {"Name": "chemicalsuperbase", "Name_Localised": "Chemical Superbase", "OwnerID": 0, "Count": 5},
                        {"Name": "circuitboard", "Name_Localised": "Circuit Board", "OwnerID": 0, "Count": 8},
                        {"Name": "circuitswitch", "Name_Localised": "Circuit Switch", "OwnerID": 0, "Count": 29},
                        {"Name": "electricalfuse", "Name_Localised": "Electrical Fuse", "OwnerID": 0, "Count": 8},
                        {"Name": "electricalwiring", "Name_Localised": "Electrical Wiring", "OwnerID": 0, "Count": 8},
                        {"Name": "encryptedmemorychip", "Name_Localised": "Encrypted Memory Chip", "OwnerID": 0,
                         "Count": 46},
                        {"Name": "epoxyadhesive", "Name_Localised": "Epoxy Adhesive", "OwnerID": 0, "Count": 7},
                        {"Name": "memorychip", "Name_Localised": "Memory Chip", "OwnerID": 0, "Count": 34},
                        {"Name": "metalcoil", "Name_Localised": "Metal Coil", "OwnerID": 0, "Count": 13},
                        {"Name": "microhydraulics", "Name_Localised": "Micro Hydraulics", "OwnerID": 0, "Count": 8},
                        {"Name": "microsupercapacitor", "Name_Localised": "Micro Supercapacitor", "OwnerID": 0,
                         "Count": 6},
                        {"Name": "microthrusters", "Name_Localised": "Micro Thrusters", "OwnerID": 0, "Count": 14},
                        {"Name": "microtransformer", "Name_Localised": "Micro Transformer", "OwnerID": 0, "Count": 11},
                        {"Name": "motor", "OwnerID": 0, "Count": 4},
                        {"Name": "opticalfibre", "Name_Localised": "Optical Fibre", "OwnerID": 0, "Count": 9},
                        {"Name": "opticallens", "Name_Localised": "Optical Lens", "OwnerID": 0, "Count": 25},
                        {"Name": "scrambler", "OwnerID": 0, "Count": 8},
                        {"Name": "titaniumplating", "Name_Localised": "Titanium Plating", "OwnerID": 0, "Count": 13},
                        {"Name": "transmitter", "OwnerID": 0, "Count": 14},
                        {"Name": "tungstencarbide", "Name_Localised": "Tungsten Carbide", "OwnerID": 0, "Count": 9},
                        {"Name": "rdx", "OwnerID": 0, "Count": 14},
                        {"Name": "electromagnet", "OwnerID": 0, "Count": 14},
                        {"Name": "oxygenicbacteria", "Name_Localised": "Oxygenic Bacteria", "OwnerID": 0, "Count": 5},
                        {"Name": "epinephrine", "OwnerID": 0, "Count": 6},
                        {"Name": "phneutraliser", "Name_Localised": "pH Neutraliser", "OwnerID": 0, "Count": 8},
                        {"Name": "microelectrode", "OwnerID": 0, "Count": 5},
                        {"Name": "ionbattery", "Name_Localised": "Ion Battery", "OwnerID": 0, "Count": 12}],
         "Consumables": [{"Name": "healthpack", "Name_Localised": "Medkit", "OwnerID": 0, "Count": 39},
                         {"Name": "energycell", "Name_Localised": "Energy Cell", "OwnerID": 0, "Count": 16},
                         {"Name": "amm_grenade_emp", "Name_Localised": "Shield Disruptor", "OwnerID": 0, "Count": 22},
                         {"Name": "amm_grenade_shield", "Name_Localised": "Shield Projector", "OwnerID": 0,
                          "Count": 57}, {"Name": "bypass", "Name_Localised": "E-Breach", "OwnerID": 0, "Count": 72}],
         "Data": [
             {"Name": "internalcorrespondence", "Name_Localised": "Internal Correspondence", "OwnerID": 0, "Count": 4},
             {"Name": "biometricdata", "Name_Localised": "Biometric Data", "OwnerID": 0, "Count": 1},
             {"Name": "nocdata", "Name_Localised": "NOC Data", "OwnerID": 0, "Count": 1},
             {"Name": "airqualityreports", "Name_Localised": "Air Quality Reports", "OwnerID": 0, "Count": 1},
             {"Name": "biologicalweapondata", "Name_Localised": "Biological Weapon Data", "OwnerID": 0, "Count": 1},
             {"Name": "catmedia", "Name_Localised": "Cat Media", "OwnerID": 0, "Count": 2},
             {"Name": "chemicalexperimentdata", "Name_Localised": "Chemical Experiment Data", "OwnerID": 0, "Count": 1},
             {"Name": "chemicalformulae", "Name_Localised": "Chemical Formulae", "OwnerID": 0, "Count": 1},
             {"Name": "chemicalinventory", "Name_Localised": "Chemical Inventory", "OwnerID": 0, "Count": 1},
             {"Name": "chemicalpatents", "Name_Localised": "Chemical Patents", "OwnerID": 0, "Count": 2},
             {"Name": "cocktailrecipes", "Name_Localised": "Cocktail Recipes", "OwnerID": 0, "Count": 1},
             {"Name": "combatantperformance", "Name_Localised": "Combatant Performance", "OwnerID": 0, "Count": 6},
             {"Name": "conflicthistory", "Name_Localised": "Conflict History", "OwnerID": 0, "Count": 1},
             {"Name": "digitaldesigns", "Name_Localised": "Digital Designs", "OwnerID": 0, "Count": 6},
             {"Name": "dutyrota", "Name_Localised": "Duty Rota", "OwnerID": 0, "Count": 3},
             {"Name": "espionagematerial", "Name_Localised": "Espionage Material", "OwnerID": 0, "Count": 1},
             {"Name": "evacuationprotocols", "Name_Localised": "Evacuation Protocols", "OwnerID": 0, "Count": 6},
             {"Name": "explorationjournals", "Name_Localised": "Exploration Journals", "OwnerID": 0, "Count": 2},
             {"Name": "extractionyielddata", "Name_Localised": "Extraction Yield Data", "OwnerID": 0, "Count": 5},
             {"Name": "factionassociates", "Name_Localised": "Faction Associates", "OwnerID": 0, "Count": 1},
             {"Name": "financialprojections", "Name_Localised": "Financial Projections", "OwnerID": 0, "Count": 2},
             {"Name": "factionnews", "Name_Localised": "Faction News", "OwnerID": 0, "Count": 1},
             {"Name": "geneticresearch", "Name_Localised": "Genetic Research", "OwnerID": 0, "Count": 2},
             {"Name": "influenceprojections", "Name_Localised": "Influence Projections", "OwnerID": 0, "Count": 1},
             {"Name": "kompromat", "OwnerID": 0, "Count": 6},
             {"Name": "maintenancelogs", "Name_Localised": "Maintenance Logs", "OwnerID": 0, "Count": 3},
             {"Name": "manufacturinginstructions", "Name_Localised": "Manufacturing Instructions", "OwnerID": 7622509,
              "Count": 4}, {"Name": "medicalrecords", "Name_Localised": "Medical Records", "OwnerID": 0, "Count": 1},
             {"Name": "medicaltrialrecords", "Name_Localised": "Clinical Trial Records", "OwnerID": 0, "Count": 2},
             {"Name": "meetingminutes", "Name_Localised": "Meeting Minutes", "OwnerID": 0, "Count": 1},
             {"Name": "mininganalytics", "Name_Localised": "Mining Analytics", "OwnerID": 0, "Count": 1},
             {"Name": "networkaccesshistory", "Name_Localised": "Network Access History", "OwnerID": 0, "Count": 1},
             {"Name": "operationalmanual", "Name_Localised": "Operational Manual", "OwnerID": 0, "Count": 5},
             {"Name": "politicalaffiliations", "Name_Localised": "Political Affiliations", "OwnerID": 0, "Count": 2},
             {"Name": "productionschedule", "Name_Localised": "Production Schedule", "OwnerID": 0, "Count": 1},
             {"Name": "propaganda", "OwnerID": 0, "Count": 2},
             {"Name": "radioactivitydata", "Name_Localised": "Radioactivity Data", "OwnerID": 0, "Count": 3},
             {"Name": "reactoroutputreview", "Name_Localised": "Reactor Output Review", "OwnerID": 0, "Count": 2},
             {"Name": "recyclinglogs", "Name_Localised": "Recycling Logs", "OwnerID": 0, "Count": 2},
             {"Name": "seedgeneaology", "Name_Localised": "Seed Geneaology", "OwnerID": 0, "Count": 1},
             {"Name": "settlementassaultplans", "Name_Localised": "Settlement Assault Plans", "OwnerID": 0, "Count": 2},
             {"Name": "shareholderinformation", "Name_Localised": "Shareholder Information", "OwnerID": 0, "Count": 2},
             {"Name": "surveilleancelogs", "Name_Localised": "Surveillance Logs", "OwnerID": 0, "Count": 2},
             {"Name": "tacticalplans", "Name_Localised": "Tactical Plans", "OwnerID": 0, "Count": 3},
             {"Name": "taxrecords", "Name_Localised": "Tax Records", "OwnerID": 0, "Count": 4},
             {"Name": "topographicalsurveys", "Name_Localised": "Topographical Surveys", "OwnerID": 0, "Count": 1},
             {"Name": "vaccineresearch", "Name_Localised": "Vaccine Research", "OwnerID": 0, "Count": 1},
             {"Name": "visitorregister", "Name_Localised": "Visitor Register", "OwnerID": 0, "Count": 1},
             {"Name": "weaponinventory", "Name_Localised": "Weapon Inventory", "OwnerID": 0, "Count": 1},
             {"Name": "xenodefenceprotocols", "Name_Localised": "Xeno-Defence Protocols", "OwnerID": 0, "Count": 1},
             {"Name": "geologicaldata", "Name_Localised": "Geological Data", "OwnerID": 0, "Count": 1},
             {"Name": "factiondonatorlist", "Name_Localised": "Faction Donator List", "OwnerID": 0, "Count": 4},
             {"Name": "pharmaceuticalpatents", "Name_Localised": "Pharmaceutical Patents", "OwnerID": 0, "Count": 1}]},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "Missions", "Active": [], "Failed": [], "Complete": []},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "Loadout", "Ship": "empire_courier", "ShipID": 88,
         "ShipName": " ", "ShipIdent": "TR-12E", "HullValue": 2542931, "ModulesValue": 9124352, "HullHealth": 1.000000,
         "UnladenMass": 61.713188, "CargoCapacity": 0, "MaxJumpRange": 50.628963,
         "FuelCapacity": {"Main": 12.000000, "Reserve": 0.410000}, "Rebuy": 583368, "Modules": [
            {"Slot": "MediumHardpoint1", "Item": "hpt_dumbfiremissilerack_fixed_small_advanced", "On": False,
             "Priority": 3, "AmmoInClip": 8, "AmmoInHopper": 64, "Health": 1.000000, "Value": 32175,
             "Engineering": {"Engineer": "Liz Ryder", "EngineerID": 300080, "BlueprintID": 128682069,
                             "BlueprintName": "Weapon_LightWeight", "Level": 4, "Quality": 0.726000, "Modifiers": [
                     {"Label": "Mass", "Value": 0.567600, "OriginalValue": 2.000000, "LessIsGood": 1},
                     {"Label": "Integrity", "Value": 20.000000, "OriginalValue": 40.000000, "LessIsGood": 0},
                     {"Label": "PowerDraw", "Value": 0.287240, "OriginalValue": 0.400000, "LessIsGood": 1},
                     {"Label": "DistributorDraw", "Value": 0.171288, "OriginalValue": 0.240000, "LessIsGood": 1}]}},
            {"Slot": "MediumHardpoint2", "Item": "hpt_dumbfiremissilerack_fixed_small_advanced", "On": False,
             "Priority": 3, "AmmoInClip": 8, "AmmoInHopper": 64, "Health": 1.000000, "Value": 32175,
             "Engineering": {"Engineer": "Liz Ryder", "EngineerID": 300080, "BlueprintID": 128682069,
                             "BlueprintName": "Weapon_LightWeight", "Level": 4, "Quality": 0.506000, "Modifiers": [
                     {"Label": "Mass", "Value": 0.639800, "OriginalValue": 2.000000, "LessIsGood": 1},
                     {"Label": "Integrity", "Value": 20.000000, "OriginalValue": 40.000000, "LessIsGood": 0},
                     {"Label": "PowerDraw", "Value": 0.299360, "OriginalValue": 0.400000, "LessIsGood": 1},
                     {"Label": "DistributorDraw", "Value": 0.173928, "OriginalValue": 0.240000, "LessIsGood": 1}]}},
            {"Slot": "MediumHardpoint3", "Item": "hpt_dumbfiremissilerack_fixed_small_advanced", "On": False,
             "Priority": 3, "AmmoInClip": 8, "AmmoInHopper": 64, "Health": 1.000000, "Value": 32175,
             "Engineering": {"Engineer": "Liz Ryder", "EngineerID": 300080, "BlueprintID": 128682069,
                             "BlueprintName": "Weapon_LightWeight", "Level": 4, "Quality": 0.518000,
                             "ExperimentalEffect": "special_weapon_lightweight",
                             "ExperimentalEffect_Localised": "Stripped Down", "Modifiers": [
                     {"Label": "Mass", "Value": 0.580140, "OriginalValue": 2.000000, "LessIsGood": 1},
                     {"Label": "Integrity", "Value": 20.000000, "OriginalValue": 40.000000, "LessIsGood": 0},
                     {"Label": "PowerDraw", "Value": 0.295000, "OriginalValue": 0.400000, "LessIsGood": 1},
                     {"Label": "DistributorDraw", "Value": 0.171648, "OriginalValue": 0.240000, "LessIsGood": 1}]}},
            {"Slot": "Armour", "Item": "empire_courier_armour_grade1", "On": True, "Priority": 1, "Health": 1.000000,
             "Engineering": {"Engineer": "Selene Jean", "EngineerID": 300210, "BlueprintID": 128673644,
                             "BlueprintName": "Armour_HeavyDuty", "Level": 5, "Quality": 0.840000,
                             "ExperimentalEffect": "special_armour_chunky",
                             "ExperimentalEffect_Localised": "Deep Plating", "Modifiers": [
                     {"Label": "DefenceModifierHealthMultiplier", "Value": 155.111115, "OriginalValue": 79.999992,
                      "LessIsGood": 0},
                     {"Label": "KineticResistance", "Value": -17.617762, "OriginalValue": -20.000004, "LessIsGood": 0},
                     {"Label": "ThermicResistance", "Value": 1.985198, "OriginalValue": 0.000000, "LessIsGood": 0},
                     {"Label": "ExplosiveResistance", "Value": -37.220718, "OriginalValue": -39.999996,
                      "LessIsGood": 0}]}},
            {"Slot": "PowerPlant", "Item": "int_powerplant_size3_class5", "On": True, "Priority": 1, "Health": 1.000000,
             "Value": 480411, "Engineering": {"Engineer": "Marco Qwent", "EngineerID": 300200, "BlueprintID": 128673773,
                                              "BlueprintName": "PowerPlant_Stealth", "Level": 4, "Quality": 0.667000,
                                              "ExperimentalEffect": "special_powerplant_cooled",
                                              "ExperimentalEffect_Localised": "Thermal Spread", "Modifiers": [
                    {"Label": "Mass", "Value": 2.900000, "OriginalValue": 2.500000, "LessIsGood": 1},
                    {"Label": "PowerCapacity", "Value": 10.559999, "OriginalValue": 12.000000, "LessIsGood": 0},
                    {"Label": "HeatEfficiency", "Value": 0.173988, "OriginalValue": 0.400000, "LessIsGood": 1}]}},
            {"Slot": "MainEngines", "Item": "int_engine_size3_class5_fast", "On": True, "Priority": 0,
             "Health": 1.000000, "Value": 5103952,
             "Engineering": {"Engineer": "Professor Palin", "EngineerID": 300220, "BlueprintID": 128673659,
                             "BlueprintName": "Engine_Dirty", "Level": 5, "Quality": 0.330000,
                             "ExperimentalEffect": "special_engine_overloaded",
                             "ExperimentalEffect_Localised": "Drag Drives", "Modifiers": [
                     {"Label": "Integrity", "Value": 46.750000, "OriginalValue": 55.000000, "LessIsGood": 0},
                     {"Label": "PowerDraw", "Value": 5.600000, "OriginalValue": 5.000000, "LessIsGood": 1},
                     {"Label": "EngineOptimalMass", "Value": 78.750000, "OriginalValue": 90.000000, "LessIsGood": 0},
                     {"Label": "EngineOptPerformance", "Value": 161.830765, "OriginalValue": 115.000000,
                      "LessIsGood": 0},
                     {"Label": "EngineHeatRate", "Value": 2.288000, "OriginalValue": 1.300000, "LessIsGood": 1}]}},
            {"Slot": "FrameShiftDrive", "Item": "int_hyperdrive_overcharge_size3_class5", "On": True, "Priority": 0,
             "Health": 1.000000, "Value": 609494,
             "Engineering": {"Engineer": "Elvira Martuuk", "EngineerID": 300160, "BlueprintID": 128673694,
                             "BlueprintName": "FSD_LongRange", "Level": 5, "Quality": 0.958000,
                             "ExperimentalEffect": "special_fsd_heavy", "ExperimentalEffect_Localised": "Mass Manager",
                             "Modifiers": [
                                 {"Label": "Mass", "Value": 6.500000, "OriginalValue": 5.000000, "LessIsGood": 1},
                                 {"Label": "Integrity", "Value": 62.560001, "OriginalValue": 80.000000,
                                  "LessIsGood": 0},
                                 {"Label": "PowerDraw", "Value": 0.517500, "OriginalValue": 0.450000, "LessIsGood": 1},
                                 {"Label": "FSDOptimalMass", "Value": 268.474518, "OriginalValue": 167.000000,
                                  "LessIsGood": 0}]}},
            {"Slot": "LifeSupport", "Item": "int_lifesupport_size1_class2", "On": True, "Priority": 0,
             "Health": 1.000000, "Value": 1293},
            {"Slot": "PowerDistributor", "Item": "int_powerdistributor_size2_class2", "On": True, "Priority": 0,
             "Health": 1.000000, "Value": 3619,
             "Engineering": {"Engineer": "Marco Qwent", "EngineerID": 300200, "BlueprintID": 128673741,
                             "BlueprintName": "PowerDistributor_PriorityEngines", "Level": 2, "Quality": 1.000000,
                             "ExperimentalEffect": "special_powerdistributor_lightweight",
                             "ExperimentalEffect_Localised": "Stripped Down", "Modifiers": [
                     {"Label": "Mass", "Value": 0.900000, "OriginalValue": 1.000000, "LessIsGood": 1},
                     {"Label": "WeaponsCapacity", "Value": 13.160000, "OriginalValue": 14.000000, "LessIsGood": 0},
                     {"Label": "WeaponsRecharge", "Value": 1.568000, "OriginalValue": 1.600000, "LessIsGood": 0},
                     {"Label": "EnginesCapacity", "Value": 14.299999, "OriginalValue": 11.000000, "LessIsGood": 0},
                     {"Label": "EnginesRecharge", "Value": 0.738000, "OriginalValue": 0.600000, "LessIsGood": 0},
                     {"Label": "SystemsCapacity", "Value": 10.340000, "OriginalValue": 11.000000, "LessIsGood": 0},
                     {"Label": "SystemsRecharge", "Value": 0.564000, "OriginalValue": 0.600000, "LessIsGood": 0}]}},
            {"Slot": "Radar", "Item": "int_sensors_size2_class2", "On": True, "Priority": 0, "Health": 1.000000,
             "Value": 3619, "Engineering": {"Engineer": "Lei Cheung", "EngineerID": 300120, "BlueprintID": 128740672,
                                            "BlueprintName": "Sensor_LightWeight", "Level": 4, "Quality": 0.540700,
                                            "Modifiers": [
                                                {"Label": "Mass", "Value": 0.418900, "OriginalValue": 1.000000,
                                                 "LessIsGood": 1},
                                                {"Label": "Integrity", "Value": 24.600000, "OriginalValue": 41.000000,
                                                 "LessIsGood": 0},
                                                {"Label": "SensorTargetScanAngle", "Value": 24.000000,
                                                 "OriginalValue": 30.000000, "LessIsGood": 0}]}},
            {"Slot": "FuelTank", "Item": "int_fueltank_size3_class3", "On": True, "Priority": 1, "Health": 1.000000},
            {"Slot": "Slot01_Size3", "Item": "int_fuelscoop_size3_class5", "On": True, "Priority": 0,
             "Health": 1.000000, "Value": 902954},
            {"Slot": "Slot02_Size3", "Item": "int_guardianfsdbooster_size3", "On": True, "Priority": 0,
             "Health": 1.000000, "Value": 1620430},
            {"Slot": "Slot03_Size2", "Item": "int_fueltank_size2_class3", "On": True, "Priority": 1, "Health": 1.000000,
             "Value": 3750},
            {"Slot": "Slot04_Size2", "Item": "int_shieldgenerator_size2_class3_fast", "On": True, "Priority": 0,
             "Health": 1.000000, "Value": 26705,
             "Engineering": {"Engineer": "Lei Cheung", "EngineerID": 300120, "BlueprintID": 128673829,
                             "BlueprintName": "ShieldGenerator_Optimised", "Level": 5, "Quality": 0.216300,
                             "ExperimentalEffect": "special_shield_efficient",
                             "ExperimentalEffect_Localised": "Lo-draw", "Modifiers": [
                     {"Label": "Mass", "Value": 1.406750, "OriginalValue": 2.500000, "LessIsGood": 1},
                     {"Label": "Integrity", "Value": 38.250000, "OriginalValue": 51.000000, "LessIsGood": 0},
                     {"Label": "PowerDraw", "Value": 0.762960, "OriginalValue": 1.500000, "LessIsGood": 1},
                     {"Label": "ShieldGenOptimalMass", "Value": 51.700001, "OriginalValue": 55.000000, "LessIsGood": 0},
                     {"Label": "ShieldGenStrength", "Value": 99.551346, "OriginalValue": 90.000000, "LessIsGood": 0},
                     {"Label": "EnergyPerRegen", "Value": 0.480000, "OriginalValue": 0.600000, "LessIsGood": 1},
                     {"Label": "KineticResistance", "Value": 39.399998, "OriginalValue": 39.999996, "LessIsGood": 0},
                     {"Label": "ThermicResistance", "Value": -21.200001, "OriginalValue": -20.000004, "LessIsGood": 0},
                     {"Label": "ExplosiveResistance", "Value": 49.500000, "OriginalValue": 50.000000,
                      "LessIsGood": 0}]}},
            {"Slot": "Slot05_Size2", "Item": "int_buggybay_size2_class2", "On": False, "Priority": 4,
             "Health": 1.000000, "Value": 21600},
            {"Slot": "Slot06_Size1", "Item": "int_detailedsurfacescanner_tiny", "On": True, "Priority": 0,
             "Health": 1.000000, "Value": 250000,
             "Engineering": {"Engineer": "Felicity Farseer", "EngineerID": 300100, "BlueprintID": 128740149,
                             "BlueprintName": "Sensor_Expanded", "Level": 3, "Quality": 0.812000, "Modifiers": [
                     {"Label": "PowerDraw", "Value": 0.000000, "OriginalValue": 0.000000, "LessIsGood": 1},
                     {"Label": "DSS_PatchRadius", "Value": 25.623999, "OriginalValue": 20.000000, "LessIsGood": 0}]}},
            {"Slot": "Slot07_Size1", "Item": "int_supercruiseassist", "On": True, "Priority": 0, "Health": 1.000000},
            {"Slot": "Slot08_Size1", "Item": "int_dockingcomputer_advanced", "On": True, "Priority": 0,
             "Health": 1.000000},
            {"Slot": "PlanetaryApproachSuite", "Item": "int_planetapproachsuite_advanced", "On": True, "Priority": 1,
             "Health": 1.000000},
            {"Slot": "VesselVoice", "Item": "voicepack_verity", "On": True, "Priority": 1, "Health": 1.000000},
            {"Slot": "ShipCockpit", "Item": "empire_courier_cockpit", "On": True, "Priority": 1, "Health": 1.000000},
            {"Slot": "CargoHatch", "Item": "modularcargobaydoor", "On": False, "Priority": 2, "Health": 1.000000}]},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "Music", "MusicTrack": "Exploration"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "Music", "MusicTrack": "NoTrack"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "Music", "MusicTrack": "Starport"},
        {"timestamp": "2024-07-18T20:50:45Z", "event": "NpcCrewPaidWage", "NpcCrewName": "George Roberson",
         "NpcCrewId": 31464544, "Amount": 0},
        {"timestamp": "2024-07-18T20:50:47Z", "event": "Cargo", "Vessel": "Ship", "Count": 0, "Inventory": []},
        {"timestamp": "2024-07-18T21:01:27Z", "event": "ReceiveText", "From": "$npc_name_decorate:#name=Solarwind;",
         "From_Localised": "Solarwind", "Message": "$Commuter_AuthorityScan05;",
         "Message_Localised": "On what grounds are you scanning this vessel, officer?", "Channel": "npc"},
        {"timestamp": "2024-07-18T21:30:23Z", "event": "ReceiveText",
         "From": "$npc_name_decorate:#name=Stephen Eilert;", "From_Localised": "Stephen Eilert",
         "Message": "$Commuter_AuthorityScan02;", "Message_Localised": "How can I be of assistance?", "Channel": "npc"},

        {"timestamp": "2024-07-17T20:50:53Z", "event": "Scanned", "ScanType": "Cargo"},
        {"timestamp": "2024-07-17T20:51:15Z", "event": "Music", "MusicTrack": "DockingComputer"},
        {"timestamp": "2024-07-17T20:51:16Z", "event": "Music", "MusicTrack": "NoTrack"},
        {
            "role": "user",
            "content": "(Commander Rude has discovered a signal using the FSS scanner. Details: {\"timestamp\": \"2024-07-18T20:50:45Z\", \"event\": \"FSSSignalDiscovered\", \"SystemAddress\": 10477373803, \"SignalName\": \"The Birthright Wars\", \"SignalType\": \"TouristBeacon\"})"
        },
        {
            "role": "user",
            "content": "(Commander Rude has discovered a signal using the FSS scanner. Details: {\"timestamp\": \"2024-07-18T20:50:45Z\", \"event\": \"FSSSignalDiscovered\", \"SystemAddress\": 10477373803, \"SignalName\": \"Chamberlain Foundation\", \"SignalType\": \"Installation\"})"
        },
        {
            "role": "user",
            "content": "(Commander Rude has discovered a signal using the FSS scanner. Details: {\"timestamp\": \"2024-07-18T20:50:45Z\", \"event\": \"FSSSignalDiscovered\", \"SystemAddress\": 10477373803, \"SignalName\": \"Gellan Scandal\", \"SignalType\": \"TouristBeacon\"})"
        },
        {
            "role": "user",
            "content": "(Commander Rude has discovered a signal using the FSS scanner. Details: {\"timestamp\": \"2024-07-18T20:50:45Z\", \"event\": \"FSSSignalDiscovered\", \"SystemAddress\": 10477373803, \"SignalName\": \"Burnell Station\", \"SignalType\": \"Outpost\"})"
        },
        {
            "role": "user",
            "content": "(Commander Rude has discovered a signal using the FSS scanner. Details: {\"timestamp\": \"2024-07-18T20:50:45Z\", \"event\": \"FSSSignalDiscovered\", \"SystemAddress\": 10477373803, \"SignalName\": \"Primary Transport Authority\", \"SignalType\": \"Installation\"})"
        },
        {
            "role": "user",
            "content": "(Commander Rude has discovered a signal using the FSS scanner. Details: {\"timestamp\": \"2024-07-18T20:50:45Z\", \"event\": \"FSSSignalDiscovered\", \"SystemAddress\": 10477373803, \"SignalName\": \"Actaea Ice Fumarole\", \"SignalType\": \"TouristBeacon\"})"
        },
        {
            "role": "user",
            "content": "So, how are things?"
        },
        {
            "content": "Aside from the galaxy dumping more tourist beacons on us than a broken travel guide, things are stellar. Located a bunch of signals, including a couple of resource extraction sites. Shall we head there, soak in some credits, and try not to get our hull too battered?",
            "role": "assistant"
        },
        {
            "role": "user",
            "content": "Oh, cool. Thank you very much."
        },
        {
            "content": "You're welcome, Commander. Good hunting. Give the word if you need any system adjustments or tactical support.",
            "role": "assistant"
        },
        {
            "role": "user",
            "content": "Can you try and move the landing gear?"
        },
        {
            "content": None,
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_Ikrg2O1jVg60laTSPp9tkyjx",
                    "function": {
                        "arguments": "{}",
                        "name": "landingGearToggle"
                    },
                    "type": "function"
                }
            ]
        },
        {
            "tool_call_id": "call_Ikrg2O1jVg60laTSPp9tkyjx",
            "role": "tool",
            "name": "landingGearToggle",
            "content": "Landing gear toggled"
        },
        {
            "role": "user",
            "content": "Can you try and use the landing gear?"
        },
        {
            "content": "The landing gear is already toggled. If you meant deploying it, that's already done. If you'd like it retracted, just let me know!",
            "role": "assistant"
        },
        {
            "role": "user",
            "content": "Yes, please do that."
        },
        {
            "content": None,
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_ZB22pnXdqJlBI3MncL35ilnE",
                    "function": {
                        "arguments": "{}",
                        "name": "landingGearToggle"
                    },
                    "type": "function"
                }
            ]
        },
        {
            "tool_call_id": "call_ZB22pnXdqJlBI3MncL35ilnE",
            "role": "tool",
            "name": "landingGearToggle",
            "content": "Landing gear toggled"
        },
        {
            "content": "Landing gear retracted, Commander. We're now ready for more nimble maneuvers.",
            "role": "assistant"
        }
    ]

    event_manager.add_conversation_event(conversation[0].get("role"), conversation[0].get("content"))
    event_manager.add_game_event(events[0])
    event_manager.add_game_event(events[1])
    event_manager.add_game_event(events[2])
    event_manager.add_conversation_event(conversation[1].get("role"), conversation[1].get("content"))
    event_manager.add_game_event(events[3])
    event_manager.add_game_event(events[4])
    event_manager.add_game_event(events[5])
    event_manager.add_game_event(events[6])
    event_manager.add_conversation_event(conversation[2].get("role"), conversation[2].get("content"))

    prompt = prompt_generator.generate_prompt(event_manager.processed)
    print(json.dumps(prompt, indent=2))
