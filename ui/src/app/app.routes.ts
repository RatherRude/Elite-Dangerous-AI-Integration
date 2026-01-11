import { Routes } from "@angular/router";
import { OverlayViewComponent } from "./overlay-view/overlay-view.component";
import { MainViewComponent } from "./main-view/main-view.component";
import { GenUiRenderComponent } from "./components/gen-ui-render/gen-ui-render.component";

export const routes: Routes = [
    { path: "", component: MainViewComponent },
    { path: "overlay", component: OverlayViewComponent },
    { path: "genui", component: GenUiRenderComponent },
];
