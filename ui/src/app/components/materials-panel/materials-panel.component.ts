import { Component, OnDestroy, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatTabsModule } from "@angular/material/tabs";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MatTooltipModule } from "@angular/material/tooltip";
import { Subscription } from "rxjs";
import { ProjectionsService } from "../../services/projections.service";

type GradeMapWithSource = {
  [grade: number]: string[];
  source?: string;
};

const RAW_CATEGORY_LABELS: Record<number, string> = {
  1: "Chemical Elements",
  2: "Heat Conductors",
  3: "Catalysts",
  4: "Crystalline Metals",
  5: "Thermal Alloys",
  6: "High-Energy Isotopes",
  7: "Exotic Elements",
};

const RAW_MATERIALS: Record<string, GradeMapWithSource> = {
  "1": { 1: ["carbon"], 2: ["vanadium"], 3: ["niobium"], 4: ["yttrium"], source: "Yttrium Crystal Shards: Outotz LS-K D8-3, planet B 5 A and Brain Trees: 35 G. Carinae, planet 2 D - trade afterwards at material trader" },
  "2": { 1: ["phosphorus"], 2: ["chromium"], 3: ["molybdenum"], 4: ["technetium"], source: "Technetium Crystal Shards: HIP 36601, planet C 5 A and Brain Trees: 35 G. Carinae, planet 2 A, HR 3230, planet 3 A A - trade afterwards at material trader" },
  "3": { 1: ["sulphur"], 2: ["manganese"], 3: ["cadmium"], 4: ["ruthenium"], source: "Ruthenium Crystal Shards: HIP 36601, planet C 1 D and Outotz LS-K D8-3, planet B 7 B and Brain Trees: 35 G. Carinae, planet 2 C - trade afterwards at material trader" },
  "4": { 1: ["iron"], 2: ["zinc"], 3: ["tin"], 4: ["selenium"], source: "Selenium Brain Trees: Kappa-1 Volantis, planet B 3 F A and HR 3230, planet 3 A A - trade afterwards at material trader" },
  "5": { 1: ["nickel"], 2: ["germanium"], 3: ["tungsten"], 4: ["tellurium"], source: "Tellurium Crystal Shards: HIP 36601, planet C 3 B and Brain Trees: Synuefe SE-V B49-4, planet B 3 A - trade afterwards at material trader" },
  "6": { 1: ["rhenium"], 2: ["arsenic"], 3: ["mercury"], 4: ["polonium"], source: "Polonium Crystal Shards: HIP 36601, planet C 1 A and Brain Trees: Synuefe AA-P C22-7, planet 5 C - trade afterwards at material trader" },
  "7": { 1: ["lead"], 2: ["zirconium"], 3: ["boron"], 4: ["antimony"], source: "Antimony Crystal Shards: Outotz LS-K D8-3, planet B 5 C and Brain Trees: 35 G. Carinae, planet 1 E - trade afterwards at material trader" },
};

const MANUFACTURED_MATERIALS: Record<string, GradeMapWithSource> = {
  Chemical: {
    1: ["chemicalstorageunits"],
    2: ["chemicalprocessors"],
    3: ["chemicaldistillery"],
    4: ["chemicalmanipulators"],
    5: ["pharmaceuticalisolators"],
    source: "High Grade Emissions (Outbreak) - trade afterwards at material trader, Mission reward",
  },
  Thermic: {
    1: ["temperedalloys"],
    2: ["heatresistantceramics"],
    3: ["precipitatedalloys"],
    4: ["thermicalloys"],
    5: ["militarygradealloys"],
    source: "High Grade Emissions (War / Civil War / Civil Unrest) - trade afterwards at material trader, Mission reward",
  },
  Heat: {
    1: ["heatconductionwiring"],
    2: ["heatdispersionplate"],
    3: ["heatexchangers"],
    4: ["heatvanes"],
    5: ["protoheatradiators"],
    source: "High Grade Emissions (Boom) - trade afterwards at material trader, Mission reward",
  },
  Conductive: {
    1: ["basicconductors"],
    2: ["conductivecomponents"],
    3: ["conductiveceramics"],
    4: ["conductivepolymers"],
    5: ["biotechconductors"],
    source: "Mission Reward",
  },
  "Mechanical Components": {
    1: ["mechanicalscrap"],
    2: ["mechanicalequipment"],
    3: ["mechanicalcomponents"],
    4: ["configurablecomponents"],
    5: ["improvisedcomponents"],
    source: "High Grade Emissions (Independent - Civil Unrest) - trade afterwards at material trader",
  },
  Capacitors: {
    1: ["gridresistors"],
    2: ["hybridcapacitors"],
    3: ["electrochemicalarrays"],
    4: ["polymercapacitors"],
    5: ["militarysupercapacitors"],
    source: "High Grade Emissions (Independent/Alliance - War / Civil War) - trade afterwards at material trader, Mission reward",
  },
  Shielding: {
    1: ["wornshieldemitters"],
    2: ["shieldemitters"],
    3: ["shieldingsensors"],
    4: ["compoundshielding"],
    5: ["imperialshielding"],
    source: "High Grade Emissions (Empire - None / Election) - trade afterwards at material trader, Mission reward",
  },
  Composite: {
    1: ["compactcomposites"],
    2: ["filamentcomposites"],
    3: ["highdensitycomposites"],
    4: ["proprietarycomposites"],
    5: ["coredynamicscomposites"],
    source: "High Grade Emissions (Federation) - trade afterwards at material trader",
  },
  Crystals: {
    1: ["crystalshards"],
    2: ["flawedfocuscrystals"],
    3: ["focuscrystals"],
    4: ["refinedfocuscrystals"],
    5: ["exquisitefocuscrystals"],
    source: "Mission reward",
  },
  Alloys: {
    1: ["salvagedalloys"],
    2: ["galvanisingalloys"],
    3: ["phasealloys"],
    4: ["protolightalloys"],
    5: ["protoradiolicalloys"],
    source: "High Grade Emissions (Boom) - trade afterwards at material trader",
  },
  "Guardian Technology": {
    1: ["guardian_sentinel_wreckagecomponents", "guardianwreckagecomponents"],
    2: ["guardian_powercell", "guardianpowercell"],
    3: ["guardian_powerconduit", "guardianpowerconduit"],
    4: ["guardian_sentinel_weaponparts", "guardiansentinelweaponparts"],
    5: ["guardian_techcomponent", "techcomponent"],
    source: "Guardian sites: Synuefe HT-F D12-29 C3, Synuefe LQ-T B50-1 B2, Synuefe GV-T B50-4 B1",
  },
  "Thargoid Technology": {
    1: ["tg_wreckagecomponents", "wreckagecomponents", "tg_abrasion02", "tgabrasion02"],
    2: ["tg_biomechanicalconduits", "biomechanicalconduits", "tg_abrasion03", "tgabrasion03"],
    3: ["tg_weaponparts", "weaponparts", "unknowncarapace", "tg_causticshard", "tgcausticshard"],
    4: ["tg_propulsionelement", "propulsionelement", "unknownenergycell", "unknowncorechip"],
    5: ["tg_causticgeneratorparts", "causticgeneratorparts", "tg_causticcrystal", "tgcausticcrystal", "unknowntechnologycomponents"],
    source: "Titan graveyards, NHSS Threat 4-5, Sensor Fragments: Solati Halla",
  },
};

const ENCODED_DEFAULT_SOURCE = "HIP 12099 — Jameson Crash Site";

const ENCODED_SECTIONS: Record<string, GradeMapWithSource> = {
  "Emission Data": {
    1: ["scrambledemissiondata"],
    2: ["archivedemissiondata"],
    3: ["emissiondata"],
    4: ["decodedemissiondata"],
    5: ["compactemissionsdata"],
    source: ENCODED_DEFAULT_SOURCE,
  },
  "Wake Scans": {
    1: ["disruptedwakeechoes"],
    2: ["fsdtelemetry"],
    3: ["wakesolutions"],
    4: ["hyperspacetrajectories"],
    5: ["dataminedwake"],
    source: ENCODED_DEFAULT_SOURCE,
  },
  "Shield Data": {
    1: ["shieldcyclerecordings"],
    2: ["shieldsoakanalysis"],
    3: ["shielddensityreports"],
    4: ["shieldpatternanalysis"],
    5: ["shieldfrequencydata"],
    source: ENCODED_DEFAULT_SOURCE,
  },
  "Encryption Files": {
    1: ["encryptedfiles"],
    2: ["encryptioncodes"],
    3: ["symmetrickeys"],
    4: ["encryptionarchives"],
    5: ["adaptiveencryptors"],
    source: ENCODED_DEFAULT_SOURCE,
  },
  "Data Archives": {
    1: ["bulkscandata"],
    2: ["scanarchives"],
    3: ["scandatabanks"],
    4: ["encodedscandata"],
    5: ["classifiedscandata"],
    source: ENCODED_DEFAULT_SOURCE,
  },
  "Encoded Firmware": {
    1: ["legacyfirmware"],
    2: ["consumerfirmware"],
    3: ["industrialfirmware"],
    4: ["securityfirmware"],
    5: ["embeddedfirmware"],
    source: ENCODED_DEFAULT_SOURCE,
  },
  "Guardian Data": {
    1: ["ancientbiologicaldata"],
    2: ["ancientculturaldata"],
    3: ["ancienthistoricaldata"],
    4: ["ancienttechnologicaldata"],
    5: ["guardian_vesselblueprint"],
    source: "Guardian obelisks: Synuefe XR-H D11-102, planet 1 B",
  },
  "Thargoid Data": {
    1: ["tg_interdictiondata"],
    2: ["tg_shipflightdata"],
    3: ["tg_shipsystemsdata"],
    4: ["tg_shutdowndata"],
    5: ["unknownshipsignature"],
    source: "Scanning Thargoid ships and wakes",
  },
};

const NON_TRADEABLE_MANUFACTURED_SECTIONS = new Set(["guardian technology", "thargoid technology"]);
const NON_TRADEABLE_ENCODED_SECTIONS = new Set(["guardian data", "thargoid data"]);

const normalizeSectionName = (section: string) => section?.trim().toLowerCase();
const isNonTradeableManufactured = (section: string) =>
  NON_TRADEABLE_MANUFACTURED_SECTIONS.has(normalizeSectionName(section));
const isNonTradeableEncoded = (section: string) =>
  NON_TRADEABLE_ENCODED_SECTIONS.has(normalizeSectionName(section));

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
  private materialCache: Record<"Raw" | "Manufactured" | "Encoded", Map<string, any[]>> = {
    Raw: new Map(),
    Manufactured: new Map(),
    Encoded: new Map(),
  };

  constructor(private projectionsService: ProjectionsService) {}

  ngOnInit(): void {
    this.subscriptions.push(
      this.projectionsService.materials$.subscribe(materials => {
        this.materials = materials;
        this.clearMaterialCaches();
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

  private canonicalMaterialName(name?: string): string {
    return (name || "")
      .toLowerCase()
      .replace(/^tg_/, "")
      .replace(/^guardian_/, "")
      .replace(/[^a-z0-9]/g, "");
  }

  private getMaterialCandidates(material: any): string[] {
    const names = [material?.Name, material?.Name_Localised].filter((value): value is string => !!value);
    const canonical = names.map(value => this.canonicalMaterialName(value)).filter(Boolean);
    return Array.from(new Set(canonical));
  }

  private getMappedMaterials(
    group: "Raw" | "Manufactured" | "Encoded",
    map: Record<string, GradeMapWithSource>,
    key: number | string,
    grade: number
  ): any[] {
    const cacheKey = `${String(key)}:${grade}`;
    const cacheBucket = this.materialCache[group];
    if (cacheBucket.has(cacheKey)) {
      return cacheBucket.get(cacheKey) || [];
    }

    const inventory = this.materials?.[group];
    const entry = map[String(key)];
    const targets = entry?.[grade]?.map(name => this.canonicalMaterialName(name)).filter(Boolean);
    if (!inventory || !targets?.length) {
      cacheBucket.set(cacheKey, []);
      return [];
    }
    const result = inventory.filter((material: any) => {
      const candidates = this.getMaterialCandidates(material);
      return candidates.some(candidate => targets.includes(candidate));
    });
    cacheBucket.set(cacheKey, result);
    return result;
  }

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
    const source = RAW_MATERIALS[String(category)]?.source;
    if (targetGrade === 4 && source) {
      parts.push(`Source: ${source}`);
    }
    return parts.join('\n');
  }

  // Manufactured totals and tooltip
  isManufacturedTradeable(section: string): boolean {
    return !isNonTradeableManufactured(section);
  }

  getManufacturedHoverTotal(section: string, targetGrade: number): number {
    const counts: { [g: number]: number } = { 1: this.getManufacturedCount(section, 1), 2: this.getManufacturedCount(section, 2), 3: this.getManufacturedCount(section, 3), 4: this.getManufacturedCount(section, 4), 5: this.getManufacturedCount(section, 5) };
    if (isNonTradeableManufactured(section)) {
      return counts[targetGrade] || 0;
    }
    return this.computeTotals(counts, targetGrade, 1, 5).finalTotal;
  }

  getManufacturedTooltip(section: string, targetGrade: number): string {
    const counts: { [g: number]: number } = { 1: this.getManufacturedCount(section, 1), 2: this.getManufacturedCount(section, 2), 3: this.getManufacturedCount(section, 3), 4: this.getManufacturedCount(section, 4), 5: this.getManufacturedCount(section, 5) };
    const parts: string[] = [];
    if (isNonTradeableManufactured(section)) {
      parts.push(`Count: ${counts[targetGrade] || 0}`);
      parts.push("Guardian / Thargoid materials cannot be traded");
    } else {
      const t = this.computeTotals(counts, targetGrade, 1, 5);
      parts.push(`Lower: +${t.upOnly}`);
      parts.push(`Higher: +${t.downOnly}`);
    }
    const source = MANUFACTURED_MATERIALS[section]?.source;
    if (targetGrade === 5 && source) {
      parts.push(`Source: ${source}`);
    }
    return parts.join('\n');
  }

  // Encoded totals and tooltip
  isEncodedTradeable(section: string): boolean {
    return !isNonTradeableEncoded(section);
  }

  getEncodedHoverTotal(section: string, targetGrade: number): number {
    const counts: { [g: number]: number } = { 1: this.getEncodedCount(section, 1), 2: this.getEncodedCount(section, 2), 3: this.getEncodedCount(section, 3), 4: this.getEncodedCount(section, 4), 5: this.getEncodedCount(section, 5) };
    if (isNonTradeableEncoded(section)) {
      return counts[targetGrade] || 0;
    }
    return this.computeTotals(counts, targetGrade, 1, 5).finalTotal;
  }

  getEncodedTooltip(section: string, targetGrade: number): string {
    const counts: { [g: number]: number } = { 1: this.getEncodedCount(section, 1), 2: this.getEncodedCount(section, 2), 3: this.getEncodedCount(section, 3), 4: this.getEncodedCount(section, 4), 5: this.getEncodedCount(section, 5) };
    const parts: string[] = [];
    if (isNonTradeableEncoded(section)) {
      parts.push(`Count: ${counts[targetGrade] || 0}`);
      parts.push("Guardian / Thargoid data cannot be traded");
    } else {
      const t = this.computeTotals(counts, targetGrade, 1, 5);
      parts.push(`Lower: +${t.upOnly}`);
      parts.push(`Higher: +${t.downOnly}`);
    }
    const source = ENCODED_SECTIONS[section]?.source;
    if (source) {
      parts.push(`Source: ${source}`);
    }
    return parts.join('\n');
  }

  // Source info maps
  // Raw material methods
  getRawMaterialByGradeAndCategory(grade: number, category: number): any[] {
    return this.getMappedMaterials("Raw", RAW_MATERIALS, category, grade);
  }

  getManufacturedMaterialByGradeAndSection(section: string, grade: number): any[] {
    return this.getMappedMaterials("Manufactured", MANUFACTURED_MATERIALS, section, grade);
  }

  getEncodedMaterialByGradeAndSection(section: string, grade: number): any[] {
    return this.getMappedMaterials("Encoded", ENCODED_SECTIONS, section, grade);
  }

  getMaterialFillPercent(count: number, grade: number): number {
    const max = this.gradeMaxByGrade[grade] ?? 100;
    const safeCount = typeof count === 'number' ? count : 0;
    const clamped = Math.max(0, Math.min(max, safeCount));
    return Math.round((clamped / max) * 100);
  }

  getRawMaterialCategoryName(category: number): string {
    return RAW_CATEGORY_LABELS[category] ?? `Category ${category}`;
  }

  getManufacturedSections(): string[] {
    return Object.keys(MANUFACTURED_MATERIALS);
  }

  getEncodedSections(): string[] {
    return Object.keys(ENCODED_SECTIONS);
  }

  getEmptyRawMaterialName(grade: number, category: number): string {
    const list = RAW_MATERIALS[String(category)]?.[grade];
    if (list && list.length > 0) {
      return this.formatMaterialName(list[0]);
    }
    return `Grade ${grade} Material`;
  }

  getEmptyManufacturedMaterialName(section: string, grade: number): string {
    const list = MANUFACTURED_MATERIALS[section]?.[grade];
    if (list && list.length > 0) {
      return this.formatMaterialName(list[0]);
    }
    return `${section} G${grade}`;
  }

  getEmptyEncodedMaterialName(section: string, grade: number): string {
    const list = ENCODED_SECTIONS[section]?.[grade];
    if (list && list.length > 0) {
      return this.formatMaterialName(list[0]);
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

  private clearMaterialCaches(): void {
    Object.values(this.materialCache).forEach(bucket => bucket.clear());
  }
}


