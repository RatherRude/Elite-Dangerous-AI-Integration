import { Routes } from "@angular/router";
import { OverlayViewComponent } from "./overlay-view/overlay-view.component";
import { MainViewComponent } from "./main-view/main-view.component";

export const routes: Routes = [
    { path: "", component: MainViewComponent },
    { path: "overlay", component: OverlayViewComponent },
];
