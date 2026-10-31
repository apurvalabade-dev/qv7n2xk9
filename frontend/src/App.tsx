import { useState } from "react";
import Accuracy from "./Accuracy";
import DeliveryDay from "./DeliveryDay";
import { useApi } from "./api";
import type { AccuracyResponse, Config } from "./types";
import { Status } from "./ui";

type Tab = "day" | "accuracy";

export default function App() {
  const [tab, setTab] = useState<Tab>("day");
  const [cutoff, setCutoff] = useState("09:20");
  const config = useApi<Config>("/api/config");
  const acc = useApi<AccuracyResponse>(`/api/accuracy?cutoff=${cutoff}`);
  const gates = config.data?.gates ?? [];

  return (
    <div className="app">
      <header>
        <h1>UK day-ahead wind forecast review</h1>
        <p className="sub">
          What the wind forecast said when the buying decision had to be made, and how far off it was. January 2026,
          national level.
        </p>
        <div className="controls">
          <label>
            Decision cutoff (day before delivery)
            <select value={cutoff} onChange={(e) => setCutoff(e.target.value)}>
              {gates.length === 0 && <option value="09:20">09:20 UTC</option>}
              {gates.map((g) => (
                <option key={g.id} value={g.cutoff}>
                  {g.cutoff} UTC · {g.label}
                </option>
              ))}
            </select>
          </label>
          <nav>
            <button className={tab === "day" ? "active" : ""} onClick={() => setTab("day")}>
              Delivery day
            </button>
            <button className={tab === "accuracy" ? "active" : ""} onClick={() => setTab("accuracy")}>
              Forecast accuracy
            </button>
          </nav>
        </div>
      </header>

      <main>
        {tab === "day" ? (
          <DeliveryDay
            cutoff={cutoff}
            first={config.data?.first_day ?? "2026-01-01"}
            last={config.data?.last_day ?? "2026-01-31"}
            byDay={acc.data?.by_day}
          />
        ) : (
          <>
            <Status loading={acc.loading} error={acc.error} />
            {acc.data && <Accuracy data={acc.data} />}
          </>
        )}
      </main>

      <footer>
        <h4>Method and limitations</h4>
        <p className="note">{config.data?.error_convention}</p>
        <ul>
          {(config.data?.limitations ?? []).map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </footer>
    </div>
  );
}