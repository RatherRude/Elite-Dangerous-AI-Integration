import { Component, OnDestroy, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";

import { MatIconModule } from "@angular/material/icon";
import { MatTabsModule } from "@angular/material/tabs";
import { MatButtonToggleModule } from "@angular/material/button-toggle";
import { MatTooltipModule } from "@angular/material/tooltip";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { StoredModulesComponent } from "../stored-modules/stored-modules.component";
import { EngineersPanelComponent } from "../engineers-panel/engineers-panel.component";
import { ProjectionsService } from "../../services/projections.service";
import { Subscription } from "rxjs";
import * as shipEngineersData from "../../../../../src/assets/ship_engineers.json";
import * as suitEngineersData from "../../../../../src/assets/suit_engineers.json";

@Component({
  selector: "app-storage-container",
  standalone: true,
  imports: [CommonModule, FormsModule, MatIconModule, MatTabsModule, MatButtonToggleModule, MatTooltipModule, MatProgressBarModule, StoredModulesComponent, EngineersPanelComponent],
  templateUrl: "./storage-container.component.html",
  styleUrl: "./storage-container.component.css",
})
export class StorageContainerComponent implements OnInit, OnDestroy {
  // Projection data
  materials: any = null;
  shipLocker: any = null;
  colonisationConstruction: any = null;
  cargo: any = null;
  shipInfo: any = null;
  storedShips: any = null;
  

  // Collapsible sections state
  sectionsCollapsed = {
    materials: false,
    shipLocker: false,
    engineers: true,
    onFootEngineers: true,
    colonisation: false,
    cargo: true,
    storedModules: true,
    storedShips: true,
  };
  
  private subscriptions: Subscription[] = [];

  // Constants
  readonly STORAGE_TAB = 'storage';

  private readonly gradeMaxByGrade: { [grade: number]: number } = { 1: 300, 2: 250, 3: 200, 4: 150, 5: 100 };
  
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

      this.projectionsService.colonisationConstruction$.subscribe(colonisation => {
        this.colonisationConstruction = colonisation;
      }),
      
      this.projectionsService.cargo$.subscribe(cargo => {
        this.cargo = cargo;
      }),
      
      this.projectionsService.shipInfo$.subscribe(shipInfo => {
        this.shipInfo = shipInfo;
      }),
      
      this.projectionsService.storedShips$.subscribe(storedShips => {
        this.storedShips = storedShips;
      })
    );
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
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

  getMaterialFillPercent(count: number, grade: number): number {
    const max = this.gradeMaxByGrade[grade] ?? 100;
    const safeCount = typeof count === 'number' ? count : 0;
    const clamped = Math.max(0, Math.min(max, safeCount));
    return Math.round((clamped / max) * 100);
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

  // Stored Ships methods
  getShipsHere(): any[] {
    return this.storedShips?.ShipsHere || [];
  }

  getShipsRemote(): any[] {
    return this.storedShips?.ShipsRemote || [];
  }

  formatTransferTime(seconds: number): string {
    if (!seconds) return '-';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  }

  
} 