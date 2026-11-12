import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { bandRelationLabel, formatReferenceNumber } from "./ranking.ts";

const data = JSON.parse(
  readFileSync(
    new URL("../../public/data/ranking.json", import.meta.url),
    "utf8",
  ),
);

test("diluição real próxima de 30% não aparece na borda quando a estimativa está dentro", () => {
  const candidate = data.candidates.find((row) => row.id === "C028");
  assert.equal(candidate.screen.pointInsideReference, true);
  assert.equal(
    formatReferenceNumber(
      candidate.predictions.DI_pct.value,
      1,
      data.window.diPct,
    ),
    "29,99",
  );
});

test("limites estritos e valores de lados opostos permanecem distinguíveis na apresentação", () => {
  assert.equal(formatReferenceNumber(10, 1, [10, 30]), "10,0");
  assert.equal(formatReferenceNumber(10.001, 1, [10, 30]), "10,001");
  assert.equal(formatReferenceNumber(9.999, 1, [10, 30]), "9,999");
  assert.equal(formatReferenceNumber(1 / 3, 3, [0.2, 1 / 3]), "1/3");
  assert.equal(formatReferenceNumber(0.3334, 3, [0.2, 1 / 3]), "0,3334");
  assert.equal(formatReferenceNumber(null, 1, [10, 30]), "—");
});

test("contato de banda com limite é conhecido, não ausência de faixa ou contenção", () => {
  assert.deepEqual(
    bandRelationLabel(
      "indicative_band_touches_reference_boundary_not_calibrated",
    ),
    { label: "A banda toca o limite estrito", tone: "crossing" },
  );
});

test("classe de borda explícita não vira ponto dentro, fora genérico ou faixa indisponível", async () => {
  const { pointReferenceLabel } = await import("./ranking.ts");
  const base = {
    pointInsideReference: false,
    pointClass: "boundary",
    status: "point_on_strict_reference_boundary",
  };
  assert.deepEqual(pointReferenceLabel(base), {
    label: "Ponto no limite",
    tone: "boundary",
  });
  assert.deepEqual(
    pointReferenceLabel({ ...base, pointClass: "unavailable", status: "not_assessable_missing_geometry_prediction" }),
    { label: "Ponto não avaliável", tone: "unknown" },
  );
});
