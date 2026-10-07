import {chromium} from 'playwright';
import assert from 'node:assert/strict';

const browser=await chromium.launch({headless:true,channel:process.env.BROWSER_CHANNEL||undefined});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const pageErrors=[];
page.on('pageerror',error=>pageErrors.push(error.message));
await page.route('**/api/**',route=>{
  const incoming=new URL(route.request().url());
  const path=incoming.pathname.replace(/^\/api/,'')+incoming.search;
  return route.continue({url:`http://127.0.0.1:8001${path}`});
});

try{
  await page.goto('http://127.0.0.1:5173');
  await page.getByRole('heading',{name:'Good trips leave room for the journey.'}).waitFor();
  assert.match(await page.getByRole('status').first().innerText(),/SYNTHETIC DEMO DATA/);

  // Inject an explicit offline/quota response at the UI boundary; no model request is sent.
  await page.route('**/api/trips/intake',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Mistral quota is exhausted. Use the structured form or add quota, then try again.'})}));
  await page.getByLabel('Describe your road trip').fill('Plan a group road trip from Coimbatore to Munnar this November');
  await page.getByRole('button',{name:'Use Trip Copilot'}).click();
  await page.getByRole('alert').filter({hasText:'Mistral quota is exhausted'}).waitFor();
  await page.unroute('**/api/trips/intake');

  // Structured road-trip form still works after the LLM provider is unavailable.
  await page.getByLabel('Must-visit places').fill('');
  await page.getByLabel('Stay / room / night (₹)').fill('2000');
  await page.getByLabel('Tolls, group (₹)').fill('300');
  await page.getByLabel('Tickets, group (₹)').fill('1200');
  await page.getByLabel('Local travel, group (₹)').fill('400');
  await page.getByRole('button',{name:'Build my road trip'}).click();
  await page.getByRole('heading',{name:'Your journey, mapped out.'}).waitFor();
  assert(['ready','partial'].includes((await page.locator('.badge').innerText()).toLowerCase()));
  assert((await page.locator('.timeline li').count())>5);
  await page.getByText('Route alternatives, costs & weather').click();
  const costs=await page.locator('.support').first().innerText();
  assert(costs.includes('accommodation: ₹4,000'));
  assert(costs.includes('tolls: ₹300'));
  assert(costs.includes('activities: ₹1,200'));
  assert(costs.includes('local transport: ₹400'));

  await page.getByRole('button',{name:'Lock',exact:true}).first().click();
  const lockedTime=await page.locator('.timeline li.locked .time').innerText();
  await page.getByRole('button',{name:'We’re 90 minutes late'}).click();
  await page.getByText('VERSION 3',{exact:false}).waitFor();
  assert.equal(await page.locator('.timeline li.locked .time').innerText(),lockedTime);

  await page.getByRole('button',{name:'Share read-only trip'}).click();
  const sharedUrl=await page.locator('.share a').getAttribute('href');
  const readOnly=await browser.newPage();
  readOnly.on('pageerror',error=>pageErrors.push(error.message));
  await readOnly.route('**/api/**',route=>{
    const incoming=new URL(route.request().url());
    return route.continue({url:`http://127.0.0.1:8001${incoming.pathname.replace(/^\/api/,'')+incoming.search}`});
  });
  await readOnly.goto(sharedUrl);
  await readOnly.getByRole('heading',{name:'Your journey, mapped out.'}).waitFor();
  assert.equal(await readOnly.getByRole('button',{name:'Lock',exact:true}).count(),0);
  await readOnly.close();

  // Unknown geography under fixtures must be shown as unavailable, never a fabricated route.
  await page.getByLabel('Starting point').fill('Delhi');
  await page.getByLabel('Destination').fill('Agra');
  const failedPlanResponse=page.waitForResponse(response=>response.url().includes('/trips/')&&response.url().endsWith('/plan')&&response.request().method()==='POST');
  await page.getByRole('button',{name:'Build my road trip'}).click();
  await failedPlanResponse;
  await page.locator('.badge.failed').waitFor();
  assert(await page.locator('.warnings').count()>0,'unavailable route must surface as an issue');
  assert.equal(await page.locator('.trip-map').count(),0,'unknown route must not draw a fabricated map');

  const widths=[];
  for(const width of [320,375,768,1024,1440]){
    await page.setViewportSize({width,height:900});
    const dimensions=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));
    widths.push({width,...dimensions});
    assert(dimensions.document<=dimensions.viewport+1,`horizontal overflow at ${width}px`);
  }
  assert.deepEqual(pageErrors,[]);
  console.log(JSON.stringify({status:'PASS',uiFlows:['Mistral quota error and form fallback','budget input and display','create plan','lock','delay preserves lock','share read-only','unknown-region failure state'],responsive:widths,pageErrors}));
}finally{await browser.close();}
