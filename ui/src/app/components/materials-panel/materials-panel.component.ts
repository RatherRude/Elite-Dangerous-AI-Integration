import { Component, OnDestroy, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatTabsModule } from "@angular/material/tabs";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MatTooltipModule } from "@angular/material/tooltip";
import { Subscription } from "rxjs";
import { ProjectionsService } from "../../services/projections.service";

@Component({
  selector: "app-materials-panel",
  standalone: true,
  imports: [CommonModule, MatTabsModule, MatProgressBarModule, MatTooltipModule],
  templateUrl: "./materials-panel.component.html",
  styleUrl: "./materials-panel.component.css",
})
export class MaterialsPanelComponent implements OnInit, OnDestroy {
  materials: any = null;

  private subscriptions: Subscription[] = [];
  hoveredKey: string | null = null;

  private readonly gradeMaxByGrade: { [grade: number]: number } = { 1: 300, 2: 250, 3: 200, 4: 150, 5: 100 };

  // Raw material mappings by category and grade
  private rawMaterialsMap: { [category: number]: { [grade: number]: string[] } } = {
    1: { 1: ['carbon'], 2: ['vanadium'], 3: ['niobium'], 4: ['yttrium'] },
    2: { 1: ['phosphorus'], 2: ['chromium'], 3: ['molybdenum'], 4: ['technetium'] },
    3: { 1: ['sulphur'], 2: ['manganese'], 3: ['cadmium'], 4: ['ruthenium'] },
    4: { 1: ['iron'], 2: ['zinc'], 3: ['tin'], 4: ['selenium'] },
    5: { 1: ['nickel'], 2: ['germanium'], 3: ['tungsten'], 4: ['tellurium'] },
    6: { 1: ['rhenium'], 2: ['arsenic'], 3: ['mercury'], 4: ['polonium'] },
    7: { 1: ['lead'], 2: ['zirconium'], 3: ['boron'], 4: ['antimony'] }
  };

  // Manufactured material mappings by section and grade
  private manufacturedMaterialsMap: { [section: string]: { [grade: number]: string[] } } = {
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
  private encodedMaterialsMap: { [section: string]: { [grade: number]: string[] } } = {
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
    this.subscriptions.push(
      this.projectionsService.materials$.subscribe(materials => {
        this.materials = materials;
      })
    );
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  // Hover key helpers
  private makeKeyRaw(category: number, grade: number, name: string): string { return `raw:${category}:${grade}:${name}`; }
  private makeKeyManufactured(section: string, grade: number, name: string): string { return `manu:${section}:${grade}:${name}`; }
  private makeKeyEncoded(section: string, grade: number, name: string): string { return `enc:${section}:${grade}:${name}`; }
  private makeKeyRawCell(category: number, grade: number): string { return `rawcell:${category}:${grade}`; }
  private makeKeyManufacturedCell(section: string, grade: number): string { return `manucell:${section}:${grade}`; }
  private makeKeyEncodedCell(section: string, grade: number): string { return `enccell:${section}:${grade}`; }

  onCellEnterRaw(category: number, grade: number, name: string): void { this.hoveredKey = this.makeKeyRaw(category, grade, name); }
  onCellEnterManufactured(section: string, grade: number, name: string): void { this.hoveredKey = this.makeKeyManufactured(section, grade, name); }
  onCellEnterEncoded(section: string, grade: number, name: string): void { this.hoveredKey = this.makeKeyEncoded(section, grade, name); }
  onCellEnterRawCell(category: number, grade: number): void { this.hoveredKey = this.makeKeyRawCell(category, grade); }
  onCellEnterManufacturedCell(section: string, grade: number): void { this.hoveredKey = this.makeKeyManufacturedCell(section, grade); }
  onCellEnterEncodedCell(section: string, grade: number): void { this.hoveredKey = this.makeKeyEncodedCell(section, grade); }
  onCellLeave(): void { this.hoveredKey = null; }

  isHoveredRaw(category: number, grade: number, name: string): boolean {
    return this.hoveredKey === this.makeKeyRaw(category, grade, name) || this.hoveredKey === this.makeKeyRawCell(category, grade);
  }
  isHoveredManufactured(section: string, grade: number, name: string): boolean {
    return this.hoveredKey === this.makeKeyManufactured(section, grade, name) || this.hoveredKey === this.makeKeyManufacturedCell(section, grade);
  }
  isHoveredEncoded(section: string, grade: number, name: string): boolean {
    return this.hoveredKey === this.makeKeyEncoded(section, grade, name) || this.hoveredKey === this.makeKeyEncodedCell(section, grade);
  }

  isHoveredRawCell(category: number, grade: number): boolean { return this.hoveredKey === this.makeKeyRawCell(category, grade); }
  isHoveredManufacturedCell(section: string, grade: number): boolean { return this.hoveredKey === this.makeKeyManufacturedCell(section, grade); }
  isHoveredEncodedCell(section: string, grade: number): boolean { return this.hoveredKey === this.makeKeyEncodedCell(section, grade); }

  // Count aggregation helpers
  private sumCount(list: any[]): number { return (list || []).reduce((t, m) => t + (m?.Count || 0), 0); }
  private getRawCount(category: number, grade: number): number { return this.sumCount(this.getRawMaterialByGradeAndCategory(grade, category)); }
  private getManufacturedCount(section: string, grade: number): number { return this.sumCount(this.getManufacturedMaterialByGradeAndSection(section, grade)); }
  private getEncodedCount(section: string, grade: number): number { return this.sumCount(this.getEncodedMaterialByGradeAndSection(section, grade)); }

  // Trading math per spec
  private computeUpContribution(count: number, steps: number): number {
    if (steps <= 0) return count || 0;
    const denom = Math.pow(6, steps);
    return Math.floor((count || 0) / denom);
  }

  private computeDownContribution(count: number, steps: number): number {
    if (steps <= 0) return count || 0;
    const factor = Math.pow(3, steps);
    return (count || 0) * factor;
  }

  private computeTotals(countsByGrade: { [g: number]: number }, target: number, minGrade: number, maxGrade: number): { current: number, upOnly: number, downOnly: number, finalTotal: number } {
    const current = countsByGrade[target] || 0;

    // Up-only cascade from lower grades into target (do not touch current or higher grades)
    const countsUp: { [g: number]: number } = {};
    for (let g = minGrade; g <= target; g++) countsUp[g] = countsByGrade[g] || 0;
    countsUp[target] = 0; // measure only contribution from lower
    for (let g = minGrade; g < target; g++) {
      const promote = Math.floor((countsUp[g] || 0) / 6);
      countsUp[g] = (countsUp[g] || 0) % 6;
      countsUp[g + 1] = (countsUp[g + 1] || 0) + promote;
    }
    const upOnly = countsUp[target] || 0;

    // Down-only: direct conversion from higher grades into target
    let downOnly = 0;
    for (let g = target + 1; g <= maxGrade; g++) {
      const steps = g - target;
      downOnly += this.computeDownContribution(countsByGrade[g] || 0, steps);
    }

    const finalTotal = current + upOnly + downOnly;
    return { current, upOnly, downOnly, finalTotal };
  }

  // RAW totals and tooltip
  getRawHoverTotal(category: number, targetGrade: number): number {
    const counts: { [g: number]: number } = { 1: this.getRawCount(category, 1), 2: this.getRawCount(category, 2), 3: this.getRawCount(category, 3), 4: this.getRawCount(category, 4) };
    return this.computeTotals(counts, targetGrade, 1, 4).finalTotal;
  }

  getRawTooltip(category: number, targetGrade: number): string {
    const counts: { [g: number]: number } = { 1: this.getRawCount(category, 1), 2: this.getRawCount(category, 2), 3: this.getRawCount(category, 3), 4: this.getRawCount(category, 4) };
    const t = this.computeTotals(counts, targetGrade, 1, 4);
    const parts: string[] = [];
    parts.push(`Lower: +${t.upOnly}`);
    parts.push(`Higher: +${t.downOnly}`);
    if (targetGrade === 4 && this.ship_raw_materials_map[category]?.source) {
      parts.push(`Source: ${this.ship_raw_materials_map[category].source}`);
    }
    return parts.join('\n');
  }

  // Manufactured totals and tooltip
  getManufacturedHoverTotal(section: string, targetGrade: number): number {
    const counts: { [g: number]: number } = { 1: this.getManufacturedCount(section, 1), 2: this.getManufacturedCount(section, 2), 3: this.getManufacturedCount(section, 3), 4: this.getManufacturedCount(section, 4), 5: this.getManufacturedCount(section, 5) };
    return this.computeTotals(counts, targetGrade, 1, 5).finalTotal;
  }

  getManufacturedTooltip(section: string, targetGrade: number): string {
    const counts: { [g: number]: number } = { 1: this.getManufacturedCount(section, 1), 2: this.getManufacturedCount(section, 2), 3: this.getManufacturedCount(section, 3), 4: this.getManufacturedCount(section, 4), 5: this.getManufacturedCount(section, 5) };
    const t = this.computeTotals(counts, targetGrade, 1, 5);
    const parts: string[] = [];
    parts.push(`Lower: +${t.upOnly}`);
    parts.push(`Higher: +${t.downOnly}`);
    if (targetGrade === 5 && this.ship_manufactured_materials_map[section]?.source) {
      parts.push(`Source: ${this.ship_manufactured_materials_map[section].source}`);
    }
    return parts.join('\n');
  }

  // Encoded totals and tooltip
  getEncodedHoverTotal(section: string, targetGrade: number): number {
    const counts: { [g: number]: number } = { 1: this.getEncodedCount(section, 1), 2: this.getEncodedCount(section, 2), 3: this.getEncodedCount(section, 3), 4: this.getEncodedCount(section, 4), 5: this.getEncodedCount(section, 5) };
    return this.computeTotals(counts, targetGrade, 1, 5).finalTotal;
  }

  getEncodedTooltip(section: string, targetGrade: number): string {
    const counts: { [g: number]: number } = { 1: this.getEncodedCount(section, 1), 2: this.getEncodedCount(section, 2), 3: this.getEncodedCount(section, 3), 4: this.getEncodedCount(section, 4), 5: this.getEncodedCount(section, 5) };
    const t = this.computeTotals(counts, targetGrade, 1, 5);
    const parts: string[] = [];
    parts.push(`Lower: +${t.upOnly}`);
    parts.push(`Higher: +${t.downOnly}`);
    if (targetGrade === 5 && this.ship_encoded_materials_location) {
      parts.push(`Source: ${this.ship_encoded_materials_location}`);
    }
    return parts.join('\n');
  }

  // Source info maps
  ship_raw_materials_map: any = {
    1: {1: ['carbon'], 2: ['vanadium'], 3: ['niobium'], 4: ['yttrium'], source: 'Yttrium Crystal Shards — Outotz LS-K D8-3 B 5 A'},
    2: {1: ['phosphorus'], 2: ['chromium'], 3: ['molybdenum'], 4: ['technetium'], source: 'Technetium Crystal Shards — HIP 36601 C 5 A'},
    3: {1: ['sulphur'], 2: ['manganese'], 3: ['cadmium'], 4: ['ruthenium'], source: 'Ruthenium Crystal Shards — HIP 36601 C 1 D; Outotz LS-K D8-3 B 7 B'},
    4: {1: ['iron'], 2: ['zinc'], 3: ['tin'], 4: ['selenium'], source: 'Selenium Brain Trees — Kappa-1 Volantis B 3 F A; HR 3230 3 A A'},
    5: {1: ['nickel'], 2: ['germanium'], 3: ['tungsten'], 4: ['tellurium'], source: 'Tellurium Crystal Shards — HIP 36601 C 3 B'},
    6: {1: ['rhenium'], 2: ['arsenic'], 3: ['mercury'], 4: ['polonium'], source: 'Polonium Crystal Shards — HIP 36601 C 1 A'},
    7: {1: ['lead'], 2: ['zirconium'], 3: ['boron'], 4: ['antimony'], source: 'Antimony Crystal Shards — Outotz LS-K D8-3 B 5 C'}
  };

  ship_manufactured_materials_map: any = {
    'Chemical': { 1: ['chemicalstorageunits'], 2: ['chemicalprocessors'], 3: ['chemicaldistillery'], 4: ['chemicalmanipulators'], 5: ['pharmaceuticalisolators'], source: 'HGE — Outbreak' },
    'Thermic': { 1: ['temperedalloys'], 2: ['heatresistantceramics'], 3: ['precipitatedalloys'], 4: ['thermicalloys'], 5: ['militarygradealloys'], source: 'HGE — War/Civil Unrest' },
    'Heat': { 1: ['heatconductionwiring'], 2: ['heatdispersionplate'], 3: ['heatexchangers'], 4: ['heatvanes'], 5: ['protoheatradiators'], source: 'HGE — Boom' },
    'Conductive': { 1: ['basicconductors'], 2: ['conductivecomponents'], 3: ['conductiveceramics'], 4: ['conductivepolymers'], 5: ['biotechconductors'], source: 'Missions' },
    'Mechanical Components': { 1: ['mechanicalscrap'], 2: ['mechanicalequipment'], 3: ['mechanicalcomponents'], 4: ['configurablecomponents'], 5: ['improvisedcomponents'], source: 'HGE — Independent (Civil Unrest)' },
    'Capacitors': { 1: ['gridresistors'], 2: ['hybridcapacitors'], 3: ['electrochemicalarrays'], 4: ['polymercapacitors'], 5: ['militarysupercapacitors'], source: 'HGE — Independent/Alliance (War/Civil War)' },
    'Shielding': { 1: ['wornshieldemitters'], 2: ['shieldemitters'], 3: ['shieldingsensors'], 4: ['compoundshielding'], 5: ['imperialshielding'], source: 'HGE — Empire (None/Election); Missions' },
    'Composite': { 1: ['compactcomposites'], 2: ['filamentcomposites'], 3: ['highdensitycomposites'], 4: ['proprietarycomposites'], 5: ['coredynamicscomposites'], source: 'HGE — Federation' },
    'Crystals': { 1: ['crystalshards'], 2: ['flawedfocuscrystals'], 3: ['focuscrystals'], 4: ['refinedfocuscrystals'], 5: ['exquisitefocuscrystals'], source: 'Missions' },
    'Alloys': { 1: ['salvagedalloys'], 2: ['galvanisingalloys'], 3: ['phasealloys'], 4: ['protolightalloys'], 5: ['protoradiolicalloys'], source: 'HGE — Boom' },
    'Guardian Technology': { 1: ['guardian_sentinel_wreckagecomponents', 'guardianwreckagecomponents'], 2: ['guardian_powercell', 'guardianpowercell'], 3: ['guardian_powerconduit', 'guardianpowerconduit'], 4: ['guardian_sentinel_weaponparts', 'guardiansentinelweaponparts'], 5: ['guardian_techcomponent', 'techcomponent'], source: 'Guardian sites — Synuefe sector' },
    'Thargoid Technology': { 1: ['tg_wreckagecomponents', 'wreckagecomponents', 'tg_abrasion02', 'tgabrasion02'], 2: ['tg_biomechanicalconduits', 'biomechanicalconduits', 'tg_abrasion03', 'tgabrasion03'], 3: ['tg_weaponparts', 'weaponparts', 'unknowncarapace', 'tg_causticshard', 'tgcausticshard'], 4: ['tg_propulsionelement', 'propulsionelement', 'unknownenergycell', 'unknowncorechip'], 5: ['tg_causticgeneratorparts', 'causticgeneratorparts', 'tg_causticcrystal', 'tgcausticcrystal', 'unknowntechnologycomponents'], source: 'Titan graveyards; NHSS 4–5; Solati Halla' }
  };

  ship_encoded_materials_location: string = 'HIP 12099 — Jameson Crash Site';

  // Raw material methods
  getRawMaterialByGradeAndCategory(grade: number, category: number): any[] {
    if (!this.materials?.Raw || !this.rawMaterialsMap[category] || !this.rawMaterialsMap[category][grade]) {
      return [];
    }

    const materialNames = this.rawMaterialsMap[category][grade];
    return this.materials.Raw.filter((material: any) => {
      const normalizedName = this.normalizeMaterialName(material.Name_Localised || material.Name);
      return materialNames.includes(normalizedName);
    });
  }

  getManufacturedMaterialByGradeAndSection(section: string, grade: number): any[] {
    if (!this.materials?.Manufactured || !this.manufacturedMaterialsMap[section] || !this.manufacturedMaterialsMap[section][grade]) {
      return [];
    }

    const materialNames = this.manufacturedMaterialsMap[section][grade];
    return this.materials.Manufactured.filter((material: any) => {
      const normalizedName = this.normalizeMaterialName(material.Name_Localised || material.Name);
      return materialNames.includes(normalizedName);
    });
  }

  getEncodedMaterialByGradeAndSection(section: string, grade: number): any[] {
    if (!this.materials?.Encoded || !this.encodedMaterialsMap[section] || !this.encodedMaterialsMap[section][grade]) {
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
    switch (category) {
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
}


