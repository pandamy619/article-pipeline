import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";
import { UiHost } from "./ui";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
    <UiHost />
  </StrictMode>,
);
