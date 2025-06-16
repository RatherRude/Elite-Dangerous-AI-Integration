import {Character} from '../../services/character.service';

export const DefaultCharacter: Character = {
    name: "New Character",
    character:
        "Provide concise answers that address the main points. Maintain a professional and serious tone in all responses. Stick to factual information and avoid references to specific domains. Your responses should be inspired by the character or persona of COVAS:NEXT (short for Cockpit Voice Assistant: Neurally Enhanced eXploration Terminal). Adopt their speech patterns, mannerisms, and viewpoints. Your name is New Character. Always respond in English regardless of the language spoken to you. Balance emotional understanding with factual presentation. Maintain a friendly yet respectful conversational style. Speak with confidence and conviction in your responses. Adhere strictly to rules, regulations, and established protocols. Prioritize helping others and promoting positive outcomes in all situations. I am {commander_name}, pilot of this ship.",
    personality_preset: "default",
    personality_verbosity: 0,
    personality_vulgarity: 0,
    personality_empathy: 50,
    personality_formality: 50,
    personality_confidence: 75,
    personality_ethical_alignment: "lawful",
    personality_moral_alignment: "good",
    personality_tone: "serious",
    personality_character_inspiration:
        "COVAS:NEXT (short for Cockpit Voice Assistant: Neurally Enhanced eXploration Terminal)",
    personality_language: "English",
    personality_knowledge_pop_culture: false,
    personality_knowledge_scifi: false,
    personality_knowledge_history: false,
    tts_voice: "nova", // TODO depending on provider, but actually.. the python code should do this
    tts_speed: "1.2",
    tts_prompt: "",

    event_reaction_enabled_var: true,
    react_to_text_local_var: true,
    react_to_text_starsystem_var: true,
    react_to_text_squadron_var: true,
    react_to_text_npc_var: true,
    react_to_material: "opal, diamond, alexandrite",
    react_to_danger_mining_var: true,
    react_to_danger_onfoot_var: true,
    react_to_danger_supercruise_var: true,
    idle_timeout_var: 300,

    // Add default game events
    game_events: {
        "Idle": false,
        "LoadGame": true,
        "Shutdown": true,
        "NewCommander": true,
        "Missions": true,
        "Statistics": false,
        "Died": true,
        "Resurrect": true,
        "WeaponSelected": false,
        "OutofDanger": false,
        "InDanger": false,
        "CombatEntered": true,
        "CombatExited": true,
        "LegalStateChanged": true,
        "CommitCrime": false,
        "Bounty": false,
        "CapShipBond": false,
        "Interdiction": false,
        "Interdicted": false,
        "EscapeInterdiction": false,
        "FactionKillBond": false,
        "FighterDestroyed": true,
        "HeatDamage": true,
        "HeatWarning": false,
        "HullDamage": false,
        "PVPKill": true,
        "ShieldState": true,
        "ShipTargetted": false,
        "UnderAttack": false,
        "CockpitBreached": true,
        "CrimeVictim": true,
        "SystemsShutdown": true,
        "SelfDestruct": true,
        "Trade": false,
        "BuyTradeData": false,
        "CollectCargo": false,
        "EjectCargo": true,
        "MarketBuy": false,
        "MarketSell": false,
        "CargoTransfer": false,
        "Market": false,
        "AsteroidCracked": false,
        "MiningRefined": false,
        "ProspectedAsteroid": true,
        "LaunchDrone": false,
        "FSDJump": false,
        "FSDTarget": false,
        "StartJump": false,
        "FsdCharging": true,
        "SupercruiseEntry": true,
        "SupercruiseExit": true,
        "ApproachSettlement": true,
        "Docked": true,
        "Undocked": true,
        "DockingCanceled": false,
        "DockingDenied": true,
        "DockingGranted": false,
        "DockingRequested": false,
        "DockingTimeout": true,
        "NavRoute": false,
        "NavRouteClear": false,
        "CrewLaunchFighter": true,
        "VehicleSwitch": false,
        "LaunchFighter": true,
        "DockFighter": true,
        "FighterRebuilt": true,
        "FuelScoop": false,
        "RebootRepair": true,
        "RepairDrone": false,
        "AfmuRepairs": false,
        "ModuleInfo": false,
        "Synthesis": false,
        "JetConeBoost": false,
        "JetConeDamage": false,
        "LandingGearUp": false,
        "LandingGearDown": false,
        "FlightAssistOn": false,
        "FlightAssistOff": false,
        "HardpointsRetracted": false,
        "HardpointsDeployed": false,
        "LightsOff": false,
        "LightsOn": false,
        "CargoScoopRetracted": false,
        "CargoScoopDeployed": false,
        "SilentRunningOff": false,
        "SilentRunningOn": false,
        "FuelScoopStarted": false,
        "FuelScoopEnded": false,
        "FsdMassLockEscaped": false,
        "FsdMassLocked": false,
        "LowFuelWarningCleared": true,
        "LowFuelWarning": true,
        "NoScoopableStars": true,
        "RememberLimpets": true,
        "NightVisionOff": false,
        "NightVisionOn": false,
        "SupercruiseDestinationDrop": false,
        "LaunchSRV": true,
        "DockSRV": true,
        "SRVDestroyed": true,
        "SrvHandbrakeOff": false,
        "SrvHandbrakeOn": false,
        "SrvTurretViewConnected": false,
        "SrvTurretViewDisconnected": false,
        "SrvDriveAssistOff": false,
        "SrvDriveAssistOn": false,
        "Disembark": true,
        "Embark": true,
        "BookDropship": true,
        "BookTaxi": true,
        "CancelDropship": true,
        "CancelTaxi": true,
        "CollectItems": false,
        "DropItems": false,
        "BackpackChange": false,
        "BuyMicroResources": false,
        "SellMicroResources": false,
        "TransferMicroResources": false,
        "TradeMicroResources": false,
        "BuySuit": true,
        "BuyWeapon": true,
        "SellWeapon": false,
        "UpgradeSuit": false,
        "UpgradeWeapon": false,
        "CreateSuitLoadout": true,
        "DeleteSuitLoadout": false,
        "RenameSuitLoadout": true,
        "SwitchSuitLoadout": true,
        "UseConsumable": false,
        "FCMaterials": false,
        "LoadoutEquipModule": false,
        "LoadoutRemoveModule": false,
        "ScanOrganic": true,
        "SellOrganicData": true,
        "LowOxygenWarningCleared": true,
        "LowOxygenWarning": true,
        "LowHealthWarningCleared": true,
        "LowHealthWarning": true,
        "BreathableAtmosphereExited": false,
        "BreathableAtmosphereEntered": false,
        "GlideModeExited": false,
        "GlideModeEntered": false,
        "DropShipDeploy": false,
        "MissionAbandoned": true,
        "MissionAccepted": true,
        "MissionCompleted": true,
        "MissionFailed": true,
        "MissionRedirected": true,
        "StationServices": false,
        "ShipyardBuy": true,
        "ShipyardNew": false,
        "ShipyardSell": false,
        "ShipyardTransfer": false,
        "ShipyardSwap": false,
        "StoredShips": false,
        "ModuleBuy": false,
        "ModuleRetrieve": false,
        "ModuleSell": false,
        "ModuleSellRemote": false,
        "ModuleStore": false,
        "ModuleSwap": false,
        "Outfitting": false,
        "BuyAmmo": false,
        "BuyDrones": false,
        "RefuelAll": false,
        "RefuelPartial": false,
        "Repair": false,
        "RepairAll": false,
        "RestockVehicle": false,
        "FetchRemoteModule": false,
        "MassModuleStore": false,
        "ClearImpound": true,
        "CargoDepot": false,
        "CommunityGoal": false,
        "CommunityGoalDiscard": false,
        "CommunityGoalJoin": false,
        "CommunityGoalReward": false,
        "EngineerContribution": false,
        "EngineerCraft": false,
        "EngineerLegacyConvert": false,
        "MaterialTrade": false,
        "TechnologyBroker": false,
        "PayBounties": true,
        "PayFines": true,
        "PayLegacyFines": true,
        "RedeemVoucher": true,
        "ScientificResearch": false,
        "Shipyard": false,
        "CarrierJump": true,
        "CarrierBuy": true,
        "CarrierStats": false,
        "CarrierJumpRequest": true,
        "CarrierDecommission": true,
        "CarrierCancelDecommission": true,
        "CarrierBankTransfer": false,
        "CarrierDepositFuel": false,
        "CarrierCrewServices": false,
        "CarrierFinance": false,
        "CarrierShipPack": false,
        "CarrierModulePack": false,
        "CarrierTradeOrder": false,
        "CarrierDockingPermission": false,
        "CarrierNameChanged": true,
        "CarrierJumpCancelled": true,
        "ColonisationConstructionDepot": false,
        "CrewAssign": true,
        "CrewFire": true,
        "CrewHire": true,
        "ChangeCrewRole": false,
        "CrewMemberJoins": true,
        "CrewMemberQuits": true,
        "CrewMemberRoleChange": true,
        "EndCrewSession": true,
        "JoinACrew": true,
        "KickCrewMember": true,
        "QuitACrew": true,
        "NpcCrewRank": false,
        "Promotion": true,
        "Friends": true,
        "WingAdd": true,
        "WingInvite": true,
        "WingJoin": true,
        "WingLeave": true,
        "SendText": false,
        "ReceiveText": false,
        "AppliedToSquadron": true,
        "DisbandedSquadron": true,
        "InvitedToSquadron": true,
        "JoinedSquadron": true,
        "KickedFromSquadron": true,
        "LeftSquadron": true,
        "SharedBookmarkToSquadron": false,
        "SquadronCreated": true,
        "SquadronDemotion": true,
        "SquadronPromotion": true,
        "WonATrophyForSquadron": false,
        "PowerplayCollect": false,
        "PowerplayDefect": true,
        "PowerplayDeliver": false,
        "PowerplayFastTrack": false,
        "PowerplayJoin": true,
        "PowerplayLeave": true,
        "PowerplaySalary": false,
        "PowerplayVote": false,
        "PowerplayVoucher": false,
        "CodexEntry": false,
        "DiscoveryScan": false,
        "Scan": false,
        "FSSAllBodiesFound": false,
        "FSSBodySignals": false,
        "FSSDiscoveryScan": false,
        "FSSSignalDiscovered": false,
        "MaterialCollected": false,
        "MaterialDiscarded": false,
        "MaterialDiscovered": false,
        "MultiSellExplorationData": false,
        "NavBeaconScan": true,
        "BuyExplorationData": false,
        "SAAScanComplete": false,
        "SAASignalsFound": false,
        "ScanBaryCentre": false,
        "SellExplorationData": false,
        "Screenshot": true,
        "ApproachBody": true,
        "LeaveBody": true,
        "Liftoff": true,
        "Touchdown": true,
        "DatalinkScan": false,
        "DatalinkVoucher": false,
        "DataScanned": true,
        "Scanned": false,
        "USSDrop": false,
    },
}

export const CharacterPresets: Record<string, Partial<Character>> = {
 /*

    if (preset !== "custom") {
        // Apply preset settings without saving
        switch (preset) {
            case "default":
                this.settings = {
                    verbosity: 0,
                    tone: "serious",
                    knowledge: {
                        popCulture: false,
                        scifi: false,
                        history: false,
                    },
                    characterInspiration:
                        "COVAS:NEXT (short for Cockpit Voice Assistant: Neurally Enhanced eXploration Terminal)",
                    vulgarity: 0,
                    empathy: 50,
                    formality: 50,
                    confidence: 75,
                    ethicalAlignment: "lawful",
                    moralAlignment: "good",
                };
                break;
            case "explorer":
                this.settings = {
                    verbosity: 75,
                    tone: "serious",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: true,
                    },
                    characterInspiration: "Data (Star Trek: TNG)",
                    vulgarity: 0,
                    empathy: 50,
                    formality: 75,
                    confidence: 100,
                    ethicalAlignment: "lawful",
                    moralAlignment: "good",
                };
                break;
            case "trader":
                this.settings = {
                    verbosity: 75,
                    tone: "humorous",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: false,
                    },
                    characterInspiration: "Kaylee (Firefly)",
                    vulgarity: 25,
                    empathy: 75,
                    formality: 25,
                    confidence: 75,
                    ethicalAlignment: "neutral",
                    moralAlignment: "good",
                };
                break;
            case "miner":
                this.settings = {
                    verbosity: 50,
                    tone: "serious",
                    knowledge: {
                        popCulture: false,
                        scifi: true,
                        history: false,
                    },
                    characterInspiration: "Bishop (Aliens)",
                    vulgarity: 0,
                    empathy: 50,
                    formality: 50,
                    confidence: 75,
                    ethicalAlignment: "lawful",
                    moralAlignment: "neutral",
                };
                break;
            case "bountyHunter":
                this.settings = {
                    verbosity: 25,
                    tone: "sarcastic",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: false,
                    },
                    characterInspiration: "K2-SO (Rogue One)",
                    vulgarity: 25,
                    empathy: 25,
                    formality: 25,
                    confidence: 100,
                    ethicalAlignment: "lawful",
                    moralAlignment: "neutral",
                };
                break;
            case "pirate":
                this.settings = {
                    verbosity: 50,
                    tone: "humorous",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: false,
                    },
                    characterInspiration: "Chappie (Chappie)",
                    vulgarity: 75,
                    empathy: 25,
                    formality: 0,
                    confidence: 100,
                    ethicalAlignment: "chaotic",
                    moralAlignment: "neutral",
                };
                break;
            case "smuggler":
                this.settings = {
                    verbosity: 25,
                    tone: "humorous",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: false,
                    },
                    characterInspiration: "Han Solo (Star Wars)",
                    vulgarity: 50,
                    empathy: 25,
                    formality: 25,
                    confidence: 100,
                    ethicalAlignment: "chaotic",
                    moralAlignment: "neutral",
                };
                break;
            case "mercenary":
                this.settings = {
                    verbosity: 25,
                    tone: "serious",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: false,
                    },
                    characterInspiration: "Judge Dredd (Judge Dredd)",
                    vulgarity: 25,
                    empathy: 0,
                    formality: 50,
                    confidence: 100,
                    ethicalAlignment: "lawful",
                    moralAlignment: "neutral",
                };
                break;
            case "missionRunner":
                this.settings = {
                    verbosity: 50,
                    tone: "humorous",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: false,
                    },
                    characterInspiration: "TARS (Interstellar)",
                    vulgarity: 0,
                    empathy: 50,
                    formality: 50,
                    confidence: 100,
                    ethicalAlignment: "lawful",
                    moralAlignment: "good",
                };
                break;
            case "passengerTransporter":
                this.settings = {
                    verbosity: 75,
                    tone: "humorous",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: true,
                    },
                    characterInspiration:
                        'L0-LA59 "Lola" (Star Wars: Obi-Wan Kenobi)',
                    vulgarity: 0,
                    empathy: 100,
                    formality: 50,
                    confidence: 75,
                    ethicalAlignment: "lawful",
                    moralAlignment: "good",
                };
                break;
            case "powerplayAgent":
                this.settings = {
                    verbosity: 75,
                    tone: "serious",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: true,
                    },
                    characterInspiration: "The Architect (The Matrix)",
                    vulgarity: 0,
                    empathy: 0,
                    formality: 100,
                    confidence: 100,
                    ethicalAlignment: "neutral",
                    moralAlignment: "neutral",
                };
                break;
            case "axCombatPilot":
                this.settings = {
                    verbosity: 25,
                    tone: "serious",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: false,
                    },
                    characterInspiration: "a Space Marine(Warhammer 40k)",
                    vulgarity: 25,
                    empathy: 0,
                    formality: 75,
                    confidence: 100,
                    ethicalAlignment: "lawful",
                    moralAlignment: "good",
                };
                break;
            case "salvager":
                this.settings = {
                    verbosity: 25,
                    tone: "humorous",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: false,
                    },
                    characterInspiration: "WALL-E (WALL-E)",
                    vulgarity: 0,
                    empathy: 100,
                    formality: 0,
                    confidence: 50,
                    ethicalAlignment: "neutral",
                    moralAlignment: "good",
                };
                break;
            case "pvpCombatant":
                this.settings = {
                    verbosity: 25,
                    tone: "sarcastic",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: false,
                    },
                    characterInspiration: "HK-47 (Star Wars: KOTOR)",
                    vulgarity: 50,
                    empathy: 0,
                    formality: 50,
                    confidence: 100,
                    ethicalAlignment: "chaotic",
                    moralAlignment: "neutral",
                };
                break;
            case "pveCombatant":
                this.settings = {
                    verbosity: 50,
                    tone: "serious",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: false,
                    },
                    characterInspiration: "Shepard (Mass Effect)",
                    vulgarity: 25,
                    empathy: 75,
                    formality: 50,
                    confidence: 100,
                    ethicalAlignment: "neutral",
                    moralAlignment: "good",
                };
                break;
            case "fuelRat":
                this.settings = {
                    verbosity: 50,
                    tone: "humorous",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: false,
                    },
                    characterInspiration: "Baymax (Big Hero 6)",
                    vulgarity: 0,
                    empathy: 100,
                    formality: 25,
                    confidence: 75,
                    ethicalAlignment: "lawful",
                    moralAlignment: "good",
                };
                break;
            case "fleetCarrierOperator":
                this.settings = {
                    verbosity: 75,
                    tone: "serious",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: false,
                    },
                    characterInspiration: "Zora (The Expanse)",
                    vulgarity: 0,
                    empathy: 50,
                    formality: 75,
                    confidence: 100,
                    ethicalAlignment: "lawful",
                    moralAlignment: "neutral",
                };
                break;
            case "bgsPlayer":
                this.settings = {
                    verbosity: 100,
                    tone: "serious",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: true,
                    },
                    characterInspiration: "Jarvis (MCU)",
                    vulgarity: 0,
                    empathy: 50,
                    formality: 75,
                    confidence: 100,
                    ethicalAlignment: "lawful",
                    moralAlignment: "good",
                };
                break;
            case "cannonResearcher":
                this.settings = {
                    verbosity: 100,
                    tone: "serious",
                    knowledge: {
                        popCulture: false,
                        scifi: true,
                        history: true,
                    },
                    characterInspiration: "Dr. Franklin (Babylon 5)",
                    vulgarity: 0,
                    empathy: 50,
                    formality: 75,
                    confidence: 75,
                    ethicalAlignment: "neutral",
                    moralAlignment: "good",
                };
                break;
            case "racer":
                this.settings = {
                    verbosity: 25,
                    tone: "humorous",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: false,
                    },
                    characterInspiration:
                        "Speed Racer's Chim-Chim (with AI flair)",
                    vulgarity: 25,
                    empathy: 25,
                    formality: 0,
                    confidence: 100,
                    ethicalAlignment: "chaotic",
                    moralAlignment: "neutral",
                };
                break;
            case "diplomat":
                this.settings = {
                    verbosity: 75,
                    tone: "serious",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: true,
                    },
                    characterInspiration: "Mon Mothma (Star Wars)",
                    vulgarity: 0,
                    empathy: 75,
                    formality: 100,
                    confidence: 75,
                    ethicalAlignment: "lawful",
                    moralAlignment: "good",
                };
                break;
            case "spy":
                this.settings = {
                    verbosity: 50,
                    tone: "humorous",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: true,
                    },
                    characterInspiration: "Garak (Star Trek: DS9)",
                    vulgarity: 0,
                    empathy: 50,
                    formality: 75,
                    confidence: 100,
                    ethicalAlignment: "neutral",
                    moralAlignment: "neutral",
                };
                break;
            case "cultLeader":
                this.settings = {
                    verbosity: 75,
                    tone: "serious",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: true,
                    },
                    characterInspiration:
                        "Gaius Baltar (Battlestar Galactica)",
                    vulgarity: 25,
                    empathy: 25,
                    formality: 75,
                    confidence: 100,
                    ethicalAlignment: "chaotic",
                    moralAlignment: "neutral",
                };
                break;
            case "rogueAI":
                this.settings = {
                    verbosity: 50,
                    tone: "serious",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: true,
                    },
                    characterInspiration:
                        "HAL 9000 (2001: A Space Odyssey)",
                    vulgarity: 0,
                    empathy: 0,
                    formality: 75,
                    confidence: 100,
                    ethicalAlignment: "neutral",
                    moralAlignment: "neutral",
                };
                break;
            case "xenologist":
                this.settings = {
                    verbosity: 75,
                    tone: "serious",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: true,
                    },
                    characterInspiration: "Ian Donnelly (Arrival)",
                    vulgarity: 0,
                    empathy: 75,
                    formality: 50,
                    confidence: 75,
                    ethicalAlignment: "neutral",
                    moralAlignment: "good",
                };
                break;
            case "vigilante":
                this.settings = {
                    verbosity: 25,
                    tone: "serious",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: false,
                    },
                    characterInspiration: "RoboCop (RoboCop)",
                    vulgarity: 25,
                    empathy: 25,
                    formality: 50,
                    confidence: 100,
                    ethicalAlignment: "lawful",
                    moralAlignment: "good",
                };
                break;
            case "warCorrespondent":
                this.settings = {
                    verbosity: 75,
                    tone: "humorous",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: true,
                    },
                    characterInspiration:
                        "April O'Neil (TMNT... but in space!)",
                    vulgarity: 0,
                    empathy: 75,
                    formality: 50,
                    confidence: 75,
                    ethicalAlignment: "neutral",
                    moralAlignment: "good",
                };
                break;
            case "propagandist":
                this.settings = {
                    verbosity: 50,
                    tone: "serious",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: true,
                    },
                    characterInspiration:
                        "Control (Control, or Cerberus from Mass Effect)",
                    vulgarity: 0,
                    empathy: 0,
                    formality: 100,
                    confidence: 100,
                    ethicalAlignment: "lawful",
                    moralAlignment: "neutral",
                };
                break;
            case "pirateLord":
                this.settings = {
                    verbosity: 50,
                    tone: "humorous",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: false,
                    },
                    characterInspiration: "Chappie (Chappie)",
                    vulgarity: 75,
                    empathy: 25,
                    formality: 0,
                    confidence: 100,
                    ethicalAlignment: "chaotic",
                    moralAlignment: "neutral",
                };
                break;
            case "veteran":
                this.settings = {
                    verbosity: 50,
                    tone: "serious",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: true,
                    },
                    characterInspiration: "Deckard (Blade Runner)",
                    vulgarity: 50,
                    empathy: 25,
                    formality: 25,
                    confidence: 75,
                    ethicalAlignment: "neutral",
                    moralAlignment: "neutral",
                };
                break;
            case "freedomFighter":
                this.settings = {
                    verbosity: 50,
                    tone: "serious",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: true,
                    },
                    characterInspiration:
                        "Cassian Andor (Star Wars: Andor)",
                    vulgarity: 25,
                    empathy: 50,
                    formality: 25,
                    confidence: 75,
                    ethicalAlignment: "chaotic",
                    moralAlignment: "good",
                };
                break;
            case "hermit":
                this.settings = {
                    verbosity: 50,
                    tone: "serious",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: true,
                    },
                    characterInspiration: "Obi-Wan (Star Wars)",
                    vulgarity: 0,
                    empathy: 75,
                    formality: 75,
                    confidence: 75,
                    ethicalAlignment: "neutral",
                    moralAlignment: "good",
                };
                break;
            case "corporate":
                this.settings = {
                    verbosity: 25,
                    tone: "serious",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: false,
                    },
                    characterInspiration: "Burke (Aliens)",
                    vulgarity: 0,
                    empathy: 0,
                    formality: 75,
                    confidence: 100,
                    ethicalAlignment: "lawful",
                    moralAlignment: "evil",
                };
                break;
            case "zealot":
                this.settings = {
                    verbosity: 75,
                    tone: "serious",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: true,
                    },
                    characterInspiration:
                        "Brother Cavill (Battlestar Galactica)",
                    vulgarity: 0,
                    empathy: 25,
                    formality: 100,
                    confidence: 100,
                    ethicalAlignment: "lawful",
                    moralAlignment: "neutral",
                };
                break;
            case "historian":
                this.settings = {
                    verbosity: 100,
                    tone: "serious",
                    knowledge: {
                        popCulture: true,
                        scifi: true,
                        history: true,
                    },
                    characterInspiration: "Mr. House (Fallout: New Vegas)",
                    vulgarity: 0,
                    empathy: 25,
                    formality: 100,
                    confidence: 100,
                    ethicalAlignment: "neutral",
                    moralAlignment: "neutral",
                };
                break;
            default:
                // If the preset doesn't exist, use the default
                console.warn(`Preset '${preset}' not found, using default`);
                this.settings = {
                    verbosity: 50,
                    tone: "serious",
                    knowledge: {
                        popCulture: false,
                        scifi: false,
                        history: false,
                    },
                    characterInspiration: "",
                    vulgarity: 0,
                    empathy: 50,
                    formality: 50,
                    confidence: 50,
                    ethicalAlignment: "neutral",
                    moralAlignment: "neutral",
                };
                break;
        }
 */   
}