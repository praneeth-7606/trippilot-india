// Opens a dedicated browser. The user signs in and fills personal fields.
// Saves only a draft; never clicks final Submit, accepts terms or opts into marketing.
import {chromium} from 'playwright';
import {tmpdir} from 'node:os';
import path from 'node:path';

const profile=path.join(tmpdir(),'opencode','trippilot-hackathon-browser');
const context=await chromium.launchPersistentContext(profile,{channel:'msedge',headless:false,
  viewport:null,args:['--remote-debugging-port=9226']});
const page=context.pages()[0]||await context.newPage();
await page.goto('https://serpapi.github.io/serpapi-india-hackathon-2026/submit.html');
console.log('Dedicated submission browser opened. Sign in using GitHub; personal fields stay manual.');
try{
  await page.locator('[data-auth-signed-in]:visible').waitFor({timeout:600000});
  const existing=await page.locator('[data-submission-list]').innerText();
  if(existing.includes('TripPilot India')){
    console.log('TripPilot India already appears in your dashboard; open its existing entry to avoid duplicates.');
  }else{
    await page.locator('[data-new-submission]').click();
    await page.locator('[data-submission-editor]:visible').waitFor();
    await page.locator('[name="project_name"]').fill('TripPilot India');
    await page.locator('[name="description"]').fill('A constraint-aware Indian group road-trip planner for cars and motorcycles. It plans the outbound journey, useful route stops, destination visits and the return deadline. Python builds and checks the schedule through LangGraph. Users inspect sources, lock activities and report delays while preserving earlier itinerary versions. The live demo plans a two-day Coimbatore–Munnar round trip for six friends on three motorcycles.');
    await page.locator('[name="track"]').selectOption({label:'Travel & Local Discovery'});
    await page.locator('[name="github_repo_url"]').fill('https://github.com/praneeth-7606/trippilot-india');
    await page.locator('[name="serpapi_usage"]').fill('Google Maps Directions (travel_mode=9 for motorcycles, 0 for cars) supplies real outbound/return routes and verifies the selected road-stop chain; the app measures the extra driving time before scheduling. Google Maps discovers attractions, restaurants, petrol stations, toilets and cafés near route/destination coordinates and returns listing evidence and weekly hours. Google Search supplies official visitor-information links. These results materially determine the timeline and feasibility checks. Timeouts, search budgets, caches and explicit unknown-data warnings bound the workflow. No bookings are made; hotel/flight searches are not implemented.');
    await page.locator('[name="ai_usage"]').fill('OpenCode powered by OpenAI gpt-6.1-sol assisted with planning, code generation, debugging, tests and documentation. The current app uses deterministic Python scheduling inside LangGraph; no in-product LLM calls are enabled.');
    await page.locator('[data-community-sources] input[value="hydpy"]').check();
    if(process.env.TRIPPILOT_DEMO_URL)await page.locator('[name="demo_url"]').fill(process.env.TRIPPILOT_DEMO_URL);
    await page.locator('[data-save-draft]').click();
    await page.waitForTimeout(2500);
    console.log('Draft save attempted. Confirm the dashboard saved it; complete your personal fields and declarations yourself.');
  }
}catch{
  console.log('Sign-in or draft preparation is still pending; the browser remains open for you.');
}
await new Promise(resolve=>context.on('close',resolve));
