import { PlaywrightCrawler, Dataset } from 'crawlee';
import fs from 'fs/promises';
import path from 'path';

// 1. More permissive regex to catch various circular link formats
const CIRCULAR_REGEX = /\/(C|CL)\d+|circular|BPRD|EPD|SMEFD/i;

const crawler = new PlaywrightCrawler({
    maxConcurrency: 5,

    async requestHandler({ page, request, enqueueLinks }) {
        console.log(`Processing: ${request.url}`);

        // DEBUG: Log all found links to understand the site structure
        const allLinks = await page.$$eval('a', (elements) => elements.map(e => e.href));
        console.log(`DEBUG: Found ${allLinks.length} anchor tags. Inspecting some:`, allLinks.slice(0, 5));

        // Use more permissive regex to catch more links
        await enqueueLinks({
            selector: 'a',
            label: 'DETAIL',
            // Update regex to be broader to capture more circulars
            regexps: [CIRCULAR_REGEX],
        });

        // If this is a detail page, save it
        if (request.userData.label === 'DETAIL' || request.url.includes('/C') || request.url.includes('/CL')) {
            const html = await page.content();
            const text = await page.locator('body').innerText();

            const urlPath = new URL(request.url).pathname;
            const filename = urlPath.replace(/\//g, '_').replace('.htm', '.txt');

            await fs.writeFile(path.join('data', 'docs', filename), text);

            await Dataset.pushData({
                url: request.url,
                filename: filename,
                scrapedAt: new Date().toISOString(),
            });
        }
    },
});

await crawler.run([
    'https://www.sbp.org.pk/bprd/2024/index.htm',
    'https://www.sbp.org.pk/smefd/circulars/2024/index.htm'
]);