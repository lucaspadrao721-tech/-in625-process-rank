import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  axisTicks,
  groupProcessPoints,
  processPoint,
  processPointTone,
} from "./process-map.ts";

const { candidates } = JSON.parse(
  readFileSync(
    new URL("../../public/data/ranking.json", import.meta.url),
    "utf8",
  ),
);

test("coordenadas são indicadores nominais com conversão min→s e g→mg", () => {
  for (const candidate of candidates) {
    const point = processPoint(candidate);
    assert.ok(point);
    assert.equal(
      point.energyJMm,
      (60 * candidate.inputs.powerW) / candidate.inputs.speedMmMin,
    );
    assert.equal(
      point.powderMgMm,
      (1000 * candidate.inputs.feedGMin) / candidate.inputs.speedMmMin,
    );
  }
});

test("sobreposição mantém todos os IDs reais, sem deslocar coordenadas", () => {
  const groups = groupProcessPoints(candidates);
  assert.equal(
    groups.flatMap((group) => group.points).length,
    candidates.length,
  );
  assert.equal(
    new Set(
      groups.flatMap((group) =>
        group.points.map(({ candidate }) => candidate.id),
      ),
    ).size,
    candidates.length,
  );
  assert.ok(groups.some((group) => group.points.length > 1));
  for (const group of groups) {
    for (const point of group.points) {
      assert.equal(point.energyJMm, group.energyJMm);
      assert.equal(point.powderMgMm, group.powderMgMm);
    }
  }
});

test("não agrupa projeções quase iguais por arredondamento", () => {
  const original = candidates.find(
    (candidate) => candidate.inputs.powerW === 300,
  );
  const nearby = {
    ...original,
    id: "TEST-NEAR",
    inputs: { ...original.inputs, powerW: original.inputs.powerW + 1e-10 },
  };
  const exactPoint = processPoint(original);
  const nearbyPoint = processPoint(nearby);
  assert.notEqual(exactPoint.energyJMm, nearbyPoint.energyJMm);
  assert.equal(groupProcessPoints([original, nearby]).length, 2);
});

test("o mapa preserva classe de borda e não colore exclusão comum como faixa", () => {
  const original = candidates[0];
  const boundary = {
    ...original,
    rankEligible: false,
    screen: { ...original.screen, pointClass: "boundary" },
  };
  const excludedInside = {
    ...original,
    rankEligible: false,
    screen: { ...original.screen, pointClass: "inside" },
  };
  const unavailable = {
    ...original,
    screen: { ...original.screen, pointClass: "unavailable" },
  };
  assert.equal(processPointTone(boundary), "boundary");
  assert.equal(processPointTone(excludedInside), "unranked");
  assert.equal(processPointTone(unavailable), "unknown");
});

test("escala abrange toda a grade e não depende dos filtros", () => {
  const points = candidates.map(processPoint);
  for (const key of ["energyJMm", "powderMgMm"]) {
    const max = Math.max(...points.map((point) => point[key]));
    const ticks = axisTicks(max);
    assert.equal(ticks[0], 0);
    assert.ok(ticks.at(-1) > max);
    assert.ok(
      ticks.every((value, index) => index === 0 || value > ticks[index - 1]),
    );
  }
});

test("entradas ausentes ou inválidas não se tornam coordenada zero", () => {
  const original = candidates[0];
  assert.equal(
    processPoint({ ...original, inputs: { ...original.inputs, powerW: null } }),
    null,
  );
  assert.equal(
    processPoint({
      ...original,
      inputs: { ...original.inputs, speedMmMin: 0 },
    }),
    null,
  );
  assert.equal(
    processPoint({
      ...original,
      inputs: { ...original.inputs, feedGMin: Infinity },
    }),
    null,
  );
});
