import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { routeGeometry, validCoordinate, cityValidation } from '../src/mapGeometry.ts';
const sample = JSON.parse(readFileSync(new URL('../src/mocks/run-samples.json', import.meta.url)));

test('accepts zero and coordinate boundaries, rejects invalid map positions', () => {
  for (const point of [[0,0],[-90,-180],[90,180]]) assert.equal(validCoordinate(...point), true);
  for (const point of [[null,0],[0,undefined],[NaN,0],[0,Infinity],[91,0],[0,-181],['37',-80]]) assert.equal(validCoordinate(...point), false);
});
test('merges coincident stops without losing their roles', () => {
  const result = routeGeometry(sample.runs[0].chain, sample.loads, sample.profile);
  const home = result.pins.find(p => p.label.includes('H'));
  assert.match(home.label, /●/); assert.match(home.label, /1P/); assert.match(home.label, /3D/);
  assert.equal(result.missingLocations.length, 0);
});
test('missing pickup is reported and never bridged with an invented connection', () => {
  const chain = { ...sample.runs[0].chain, loads: ['a','b'] };
  const place = (city, lat, lng) => ({city,lat,lng});
  const profile = {...sample.profile, home:place('Home, VA',1,1),current_location:place('Start, VA',2,2)};
  const loads = [{id:'a',origin:place('Missing, VA',null,null),destination:place('Drop, VA',3,3)}, {id:'b',origin:place('Next, VA',4,4),destination:place('End, VA',5,5)}];
  const result = routeGeometry(chain,loads,profile);
  assert.deepEqual(result.missingLocations,['1P: Missing, VA']);
  assert.deepEqual(result.lines.map(l=>l.positions), [[[3,3],[4,4]],[[4,4],[5,5]],[[5,5],[1,1]]]);
});
test('route identity ignores economics and changes with selected loads or coordinates', () => {
  const chain = sample.runs[0].chain;
  const base = routeGeometry(chain,sample.loads,sample.profile).routeKey;
  assert.equal(base,routeGeometry({...chain,total_net_profit:0},structuredClone(sample.loads),structuredClone(sample.profile)).routeKey);
  assert.notEqual(base,routeGeometry({...chain,loads:[...chain.loads].reverse()},sample.loads,sample.profile).routeKey);
  const profile=structuredClone(sample.profile);profile.home.lat+=1;
  assert.notEqual(base,routeGeometry(chain,sample.loads,profile).routeKey);
});
test('missing load is reported and breaks the previous connection', () => {
  const chain={...sample.runs[0].chain,loads:['missing']};
  const result=routeGeometry(chain,sample.loads,sample.profile);
  assert.deepEqual(result.lines,[]);assert.match(result.missingLocations[0],/missing/);
});
test('city input requires a name and state without rejecting punctuation', () => {
  for(const city of ['Richmond, VA', "St. John's, FL",' Winston-Salem, NC ']) assert.equal(cityValidation(city),'');
  for(const city of ['', '  ', ' , VA','Richmond','Richmond, Virginia','A, B, VA']) assert.notEqual(cityValidation(city),'');
});
