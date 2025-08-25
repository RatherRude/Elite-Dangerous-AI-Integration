import { Component } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatIconModule } from "@angular/material/icon";
import * as engineeringData from "../../../../../src/assets/engineering_modifications.json";

type BlueprintMap = Record<string, any>;

@Component({
  selector: "app-engineering-blueprints",
  standalone: true,
  imports: [CommonModule, FormsModule, MatIconModule],
  templateUrl: "./engineering-blueprints.component.html",
  styleUrl: "./engineering-blueprints.component.css",
})
export class EngineeringBlueprintsComponent {
  searchTerm: string = '';
  // Loaded JSON
  data: BlueprintMap = (engineeringData as any) as BlueprintMap;

  getAllBlueprintNames(): string[] {
    return Object.keys(this.data || {});
  }

  formatName(name: string): string {
    if (!name) return '';
    return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  isExperimental(modName: string): boolean {
    const entry = this.data[modName];
    return Boolean(entry?.experimental);
  }

  getFilteredBlueprintNames(): string[] {
    const term = (this.searchTerm || '').toLowerCase();
    const names = this.getAllBlueprintNames();
    if (!term) return names;
    return names.filter((modName) => {
      const entry = this.data[modName];
      if (!entry) return false;
      if (modName.toLowerCase().includes(term)) return true;
      const modules = Object.keys(entry.module_recipes || {});
      if (modules.some(m => m.toLowerCase().includes(term))) return true;
      // search engineers
      const engineerHit = modules.some(m => {
        const grades = entry.module_recipes[m];
        return Object.values(grades).some((g: any) => Array.isArray(g.engineers) && g.engineers.some((e: string) => e.toLowerCase().includes(term)));
      });
      return engineerHit;
    });
  }

  getModulesFor(modName: string): string[] {
    const entry = this.data[modName];
    return Object.keys(entry?.module_recipes || {});
  }

  getModulesForFiltered(modName: string): string[] {
    const modules = this.getModulesFor(modName);
    const term = (this.searchTerm || '').toLowerCase();
    if (!term) return modules;
    const matches = modules.filter(m => m.toLowerCase().includes(term));
    // If the search term matches module names within this blueprint, only show those modules
    return matches.length > 0 ? matches : modules;
  }

  getGradesFor(modName: string, moduleName: string): Array<{ grade: string; cost: Record<string, number> | Record<string, number>[]; engineers: string[] }>{
    const grades = this.data[modName]?.module_recipes?.[moduleName] || {};
    // Normalize into array of rows
    return Object.keys(grades).map((g) => ({
      grade: g,
      cost: (grades[g] as any).cost,
      engineers: (grades[g] as any).engineers || [],
    })).sort((a, b) => Number(a.grade) - Number(b.grade));
  }

  // Template helpers
  getCostLines(cost: any): Array<Record<string, number>> {
    if (!cost) return [];
    if (Array.isArray(cost)) return cost as Array<Record<string, number>>;
    return [cost as Record<string, number>];
  }

  getObjectKeys(obj: Record<string, any>): string[] {
    if (!obj) return [];
    return Object.keys(obj);
  }
}


