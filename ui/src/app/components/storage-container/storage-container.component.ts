import { Component, OnDestroy, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";

import { MatIconModule } from "@angular/material/icon";
import { MatTabsModule } from "@angular/material/tabs";
import { MatButtonToggleModule } from "@angular/material/button-toggle";
import { MatTooltipModule } from "@angular/material/tooltip";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { ProjectionsService } from "../../services/projections.service";
import { Subscription } from "rxjs";
import * as shipEngineersData from "../../../../../src/assets/ship_engineers.json";
import * as suitEngineersData from "../../../../../src/assets/suit_engineers.json";

@Component({
  selector: "app-storage-container",
  standalone: true,
  imports: [CommonModule, FormsModule, MatIconModule, MatTabsModule, MatButtonToggleModule, MatTooltipModule, MatProgressBarModule],
  templateUrl: "./storage-container.component.html",
  styleUrl: "./storage-container.component.css",
})
export class StorageContainerComponent implements OnInit, OnDestroy {
  // Projection data
  materials: any = null;
  shipLocker: any = null;
  engineerProgress: any = null;
  colonisationConstruction: any = null;
  cargo: any = null;
  shipInfo: any = null;
  
  // UI state
  engineerFilter: string = 'all';
  onFootEngineerFilter: string = 'all';
  
  // Collapsible sections state
  sectionsCollapsed = {
    materials: false,
    shipLocker: false,
    engineers: false,
    onFootEngineers: false,
    colonisation: false,
    cargo: false
  };
  
  private subscriptions: Subscription[] = [];

  // Constants
  readonly STORAGE_TAB = 'storage';

  // Raw material mappings by category and grade
  private rawMaterialsMap: {[category: number]: {[grade: number]: string[]}} = {
    1: { 1: ['carbon'], 2: ['vanadium'], 3: ['niobium'], 4: ['yttrium'] },
    2: { 1: ['phosphorus'], 2: ['chromium'], 3: ['molybdenum'], 4: ['technetium'] },
    3: { 1: ['sulphur'], 2: ['manganese'], 3: ['cadmium'], 4: ['ruthenium'] },
    4: { 1: ['iron'], 2: ['zinc'], 3: ['tin'], 4: ['selenium'] },
    5: { 1: ['nickel'], 2: ['germanium'], 3: ['tungsten'], 4: ['tellurium'] },
    6: { 1: ['rhenium'], 2: ['arsenic'], 3: ['mercury'], 4: ['polonium'] },
    7: { 1: ['lead'], 2: ['zirconium'], 3: ['boron'], 4: ['antimony'] }
  };

  // Manufactured material mappings by section and grade
  private manufacturedMaterialsMap: {[section: string]: {[grade: number]: string[]}} = {
    'Chemical': {
      1: ['chemicalstorageunits'],
      2: ['chemicalprocessors'],
      3: ['chemicaldistillery'],
      4: ['chemicalmanipulators'],
      5: ['pharmaceuticalisolators']
    },
    'Thermic': {
      1: ['temperedalloys'],
      2: ['heatresistantceramics'],
      3: ['precipitatedalloys'],
      4: ['thermicalloys'],
      5: ['militarygradealloys']
    },
    'Heat': {
      1: ['heatconductionwiring'],
      2: ['heatdispersionplate'],
      3: ['heatexchangers'],
      4: ['heatvanes'],
      5: ['protoheatradiators']
    },
    'Conductive': {
      1: ['basicconductors'],
      2: ['conductivecomponents'],
      3: ['conductiveceramics'],
      4: ['conductivepolymers'],
      5: ['biotechconductors']
    },
    'Mechanical Components': {
      1: ['mechanicalscrap'],
      2: ['mechanicalequipment'],
      3: ['mechanicalcomponents'],
      4: ['configurablecomponents'],
      5: ['improvisedcomponents']
    },
    'Capacitors': {
      1: ['gridresistors'],
      2: ['hybridcapacitors'],
      3: ['electrochemicalarrays'],
      4: ['polymercapacitors'],
      5: ['militarysupercapacitors']
    },
    'Shielding': {
      1: ['wornshieldemitters'],
      2: ['shieldemitters'],
      3: ['shieldingsensors'],
      4: ['compoundshielding'],
      5: ['imperialshielding']
    },
    'Composite': {
      1: ['compactcomposites'],
      2: ['filamentcomposites'],
      3: ['highdensitycomposites'],
      4: ['proprietarycomposites'],
      5: ['coredynamicscomposites']
    },
    'Crystals': {
      1: ['crystalshards'],
      2: ['flawedfocuscrystals'],
      3: ['focuscrystals'],
      4: ['refinedfocuscrystals'],
      5: ['exquisitefocuscrystals']
    },
    'Alloys': {
      1: ['salvagedalloys'],
      2: ['galvanisingalloys'],
      3: ['phasealloys'],
      4: ['protolightalloys'],
      5: ['protoradiolicalloys']
    }
  };

  // Encoded material mappings by section and grade
  private encodedMaterialsMap: {[section: string]: {[grade: number]: string[]}} = {
    'Emission Data': {
      1: ['exceptionalscrambledemissiondata'],
      2: ['irregularemissiondata'],
      3: ['unexpectedemissiondata'],
      4: ['decodedemissiondata'],
      5: ['abnormalcompactemissionsdata']
    },
    'Wake Scans': {
      1: ['atypicaldisruptedwakeechoes'],
      2: ['anomalousfsdtelemetry'],
      3: ['strangewakesolutions'],
      4: ['eccentrichyperspace'],
      5: ['dataminedwakeexceptions']
    },
    'Shield Data': {
      1: ['distortedshieldcyclerecordings'],
      2: ['inconsistentshieldsoakanalysis'],
      3: ['untypicalshieldscans'],
      4: ['aberrantshieldpatternanalysis'],
      5: ['peculiarshieldfrequencydata']
    },
    'Encryption Files': {
      1: ['unusualencryptedfiles'],
      2: ['taggedencryptioncodes'],
      3: ['opensymmetrickeys'],
      4: ['atypicalencryptionarchives'],
      5: ['adaptiveencryptorscapture']
    },
    'Data Archives': {
      1: ['anomalousbulkscandata'],
      2: ['unidentifiedscanarchives'],
      3: ['classifiedscandatabanks'],
      4: ['divergentscandata'],
      5: ['classifiedscanfragment']
    },
    'Encoded Firmware': {
      1: ['specialisedlegacyfirmware'],
      2: ['modifiedconsumerfirmware'],
      3: ['crackedindustrialfirmware'],
      4: ['securityfirmwarepatch'],
      5: ['modifiedembeddedfirmware']
    }
  };

  // Engineer databases from JSON files
  private shipEngineersDB = shipEngineersData;
  private suitEngineersDB = suitEngineersData;

  constructor(private projectionsService: ProjectionsService) {}

  ngOnInit(): void {
    // Subscribe to relevant projections
    this.subscriptions.push(
      this.projectionsService.materials$.subscribe(materials => {
        this.materials = materials;
      }),
      
      this.projectionsService.shipLocker$.subscribe(shipLocker => {
        this.shipLocker = shipLocker;
      }),
      
      this.projectionsService.engineerProgress$.subscribe(engineerProgress => {
        this.engineerProgress = engineerProgress;
      }),
      
      this.projectionsService.colonisationConstruction$.subscribe(colonisation => {
        this.colonisationConstruction = colonisation;
      }),
      
      this.projectionsService.cargo$.subscribe(cargo => {
        this.cargo = cargo;
      }),
      
      this.projectionsService.shipInfo$.subscribe(shipInfo => {
        this.shipInfo = shipInfo;
      })
    );
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  // Projection helper method
  getProjection(name: string): any {
    const projectionMap: Record<string, any> = {
      'Materials': this.materials,
      'ShipLocker': this.shipLocker,
      'EngineerProgress': this.engineerProgress
    };
    return projectionMap[name] || null;
  }

  // Raw material methods
  getRawMaterialByGradeAndCategory(grade: number, category: number): any[] {
    if (!this.materials?.Raw ||
        !this.rawMaterialsMap[category] ||
        !this.rawMaterialsMap[category][grade]) {
      return [];
    }

    const materialNames = this.rawMaterialsMap[category][grade];
    return this.materials.Raw.filter((material: any) => {
      const normalizedName = this.normalizeMaterialName(material.Name_Localised || material.Name);
      return materialNames.includes(normalizedName);
    });
  }

  getManufacturedMaterialByGradeAndSection(section: string, grade: number): any[] {
    if (!this.materials?.Manufactured ||
        !this.manufacturedMaterialsMap[section] ||
        !this.manufacturedMaterialsMap[section][grade]) {
      return [];
    }

    const materialNames = this.manufacturedMaterialsMap[section][grade];
    return this.materials.Manufactured.filter((material: any) => {
      const normalizedName = this.normalizeMaterialName(material.Name_Localised || material.Name);
      return materialNames.includes(normalizedName);
    });
  }

  getEncodedMaterialByGradeAndSection(section: string, grade: number): any[] {
    if (!this.materials?.Encoded ||
        !this.encodedMaterialsMap[section] ||
        !this.encodedMaterialsMap[section][grade]) {
      return [];
    }

    const materialNames = this.encodedMaterialsMap[section][grade];
    return this.materials.Encoded.filter((material: any) => {
      const normalizedName = this.normalizeMaterialName(material.Name_Localised || material.Name);
      return materialNames.includes(normalizedName);
    });
  }

  private normalizeMaterialName(name: string): string {
    return name.toLowerCase()
      .replace(/^tg_/, '')
      .replace(/^guardian_/, '')
      .replace(/[^a-z0-9]/g, '');
  }

  getRawMaterialCategoryName(category: number): string {
    switch(category) {
      case 1: return "Carbon-based";
      case 2: return "Metals";
      case 3: return "Non-Metals";
      case 4: return "Crystalline Structures";
      case 5: return "Thermic";
      case 6: return "Organics";
      case 7: return "Xenobiologicals";
      default: return `Category ${category}`;
    }
  }

  getManufacturedSections(): string[] {
    return Object.keys(this.manufacturedMaterialsMap);
  }

  getEncodedSections(): string[] {
    return Object.keys(this.encodedMaterialsMap);
  }

  getEmptyRawMaterialName(grade: number, category: number): string {
    if (this.rawMaterialsMap[category] && this.rawMaterialsMap[category][grade] && this.rawMaterialsMap[category][grade].length > 0) {
      return this.formatMaterialName(this.rawMaterialsMap[category][grade][0]);
    }
    return `Grade ${grade} Material`;
  }

  getEmptyManufacturedMaterialName(section: string, grade: number): string {
    if (this.manufacturedMaterialsMap[section] && this.manufacturedMaterialsMap[section][grade] && this.manufacturedMaterialsMap[section][grade].length > 0) {
      return this.formatMaterialName(this.manufacturedMaterialsMap[section][grade][0]);
    }
    return `${section} G${grade}`;
  }

  getEmptyEncodedMaterialName(section: string, grade: number): string {
    if (this.encodedMaterialsMap[section] && this.encodedMaterialsMap[section][grade] && this.encodedMaterialsMap[section][grade].length > 0) {
      return this.formatMaterialName(this.encodedMaterialsMap[section][grade][0]);
    }
    return `${section} G${grade}`;
  }

  formatMaterialName(name: string): string {
    if (!name) return '';
    return name
      .replace(/_/g, ' ')
      .replace(/([A-Z])/g, ' $1')
      .replace(/\w\S*/g, txt => txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase());
  }

  formatItemName(name: string): string {
    if (!name) return '';
    return this.formatMaterialName(name);
  }

  // Engineer methods
  getFilteredShipEngineers(): any[] {
    const knownEngineers = this.engineerProgress?.Engineers || [];
    
    // Get all ship engineers (EngineerID 300xxx) from projection data
    const shipEngineersFromData = knownEngineers.filter((e: any) => 
      e.EngineerID >= 300000 && e.EngineerID < 400000
    );

    // Merge with static data for additional info, using projection data as primary source
    const mergedEngineers = shipEngineersFromData.map((projectionEngineer: any) => {
      const staticEngineer = (this.shipEngineersDB as any)[projectionEngineer.EngineerID.toString()];
      return staticEngineer ? { ...staticEngineer, ...projectionEngineer } : projectionEngineer;
    });

    // Apply filter
    if (this.engineerFilter === 'all') {
      return mergedEngineers;
    } else if (this.engineerFilter === 'locked') {
      return mergedEngineers.filter((e: any) => !e.Progress);
    } else {
      return mergedEngineers.filter((e: any) => e.Progress === this.engineerFilter.charAt(0).toUpperCase() + this.engineerFilter.slice(1));
    }
  }

  getFilteredOnFootEngineers(): any[] {
    const knownEngineers = this.engineerProgress?.Engineers || [];
    
    // Get all on-foot engineers (EngineerID 400xxx) from projection data
    const onFootEngineersFromData = knownEngineers.filter((e: any) => 
      e.EngineerID >= 400000 && e.EngineerID < 500000
    );

    // Merge with static data for additional info, using projection data as primary source
    const mergedEngineers = onFootEngineersFromData.map((projectionEngineer: any) => {
      const staticEngineer = (this.suitEngineersDB as any)[projectionEngineer.EngineerID.toString()];
      return staticEngineer ? { ...staticEngineer, ...projectionEngineer } : projectionEngineer;
    });

    // Apply filter
    if (this.onFootEngineerFilter === 'all') {
      return mergedEngineers;
    } else if (this.onFootEngineerFilter === 'locked') {
      return mergedEngineers.filter((e: any) => !e.Progress);
    } else {
      return mergedEngineers.filter((e: any) => e.Progress === this.onFootEngineerFilter.charAt(0).toUpperCase() + this.onFootEngineerFilter.slice(1));
    }
  }

  getEngineerModules(engineerName: string): string {
    // Find ship engineer by name
    const shipEngineerEntry = Object.values(this.shipEngineersDB).find((e: any) => e.Engineer === engineerName);
    if (shipEngineerEntry) {
      if (typeof shipEngineerEntry.Modifies === 'object') {
        return Object.keys(shipEngineerEntry.Modifies).join(', ');
      }
      return shipEngineerEntry.Modifies || 'Unknown';
    }
    return 'Unknown';
  }

  getOnFootEngineerModules(engineerName: string): string {
    // Find suit engineer by name
    const suitEngineerEntry = Object.values(this.suitEngineersDB).find((e: any) => e.Engineer === engineerName);
    if (suitEngineerEntry) {
      if (typeof suitEngineerEntry.Modifies === 'object') {
        return Object.keys(suitEngineerEntry.Modifies).join(', ');
      }
      return suitEngineerEntry.Modifies || 'Unknown';
    }
    return 'Unknown';
  }

  getEngineerLocation(engineerName: string): string {
    // Check ship engineers first
    const shipEngineerEntry = Object.values(this.shipEngineersDB).find((e: any) => e.Engineer === engineerName);
    if (shipEngineerEntry) return shipEngineerEntry.Location;

    // Check suit engineers
    const suitEngineerEntry = Object.values(this.suitEngineersDB).find((e: any) => e.Engineer === engineerName);
    return suitEngineerEntry?.Location || 'Unknown';
  }

  getArray(length: number): any[] {
    return new Array(length);
  }

  // Collapsible section methods
  toggleSection(section: keyof typeof this.sectionsCollapsed): void {
    this.sectionsCollapsed[section] = !this.sectionsCollapsed[section];
  }

  // Colonisation methods
  isColonisationActive(): boolean {
    return this.colonisationConstruction && this.colonisationConstruction.StarSystem && this.colonisationConstruction.StarSystem !== 'Unknown';
  }

  getColonisationSystem(): string {
    return this.colonisationConstruction?.StarSystem || 'Unknown System';
  }

  getColonisationStatusText(): string {
    if (this.colonisationConstruction?.ConstructionComplete) return 'Complete';
    if (this.colonisationConstruction?.ConstructionFailed) return 'Failed';
    return 'In Progress';
  }

  getColonisationStatusClass(): string {
    if (this.colonisationConstruction?.ConstructionComplete) return 'status-complete';
    if (this.colonisationConstruction?.ConstructionFailed) return 'status-failed';
    return 'status-active';
  }

  getColonisationProgress(): number {
    return this.colonisationConstruction?.ConstructionProgress || 0;
  }

  getColonisationProgressValue(): number {
    return this.getColonisationProgress() * 100;
  }

  getColonisationResources(): any[] {
    return this.colonisationConstruction?.ResourcesRequired || [];
  }

  formatPercentage(value: number): string {
    return `${(value * 100).toFixed(1)}%`;
  }

  // Cargo methods
  getCargoItems(): any[] {
    return this.cargo?.Inventory || [];
  }

  hasCargoItems(): boolean {
    return this.getCargoItems().length > 0;
  }

  getCargoAmount(): number {
    return this.getCargoItems().reduce((total, item) => total + (item.Count || 0), 0);
  }

  getCargoCapacity(): number {
    return this.shipInfo?.CargoCapacity || this.cargo?.Capacity || 0;
  }

  getCargoPercentage(): number {
    const capacity = this.getCargoCapacity();
    if (capacity === 0) return 0;
    return (this.getCargoAmount() / capacity) * 100;
  }

  formatNumber(num: number): string {
    return num.toLocaleString();
  }
} 