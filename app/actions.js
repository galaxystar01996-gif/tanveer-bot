'use server';

import { prisma } from '@/lib/prisma';
import { revalidatePath } from 'next/cache';
// This function parses the URL you paste in
function getProductDetails(url, partNumber) {
  try {
    const parsedUrl = new URL(url);

    // --- NEW FLIPKART LOGIC ---
    if (parsedUrl.hostname.includes('flipkart.com')) {
      const pid = parsedUrl.searchParams.get('pid');
      if (!pid) {
        throw new Error('Flipkart URL is missing a "pid" query parameter.');
      }
      const name = (parsedUrl.pathname.split('/')[1] || 'Flipkart Product')
                   .replace(/-/g, ' ').slice(0, 50) + '...';
      return {
        name: `(Flipkart) ${name}`,
        productId: pid, // For Flipkart, the PID is the Product ID
        storeType: 'flipkart',
        partNumber: null
      };
    }

    // --- AMAZON LOGIC ---
    if (parsedUrl.hostname.includes('amazon.in')) {
      const pathParts = parsedUrl.pathname.split('/');
      const dpIndex = pathParts.indexOf('dp');
      if (dpIndex === -1 || !pathParts[dpIndex + 1]) {
        throw new Error('Could not find a valid ASIN in the Amazon URL.');
      }
      const asin = pathParts[dpIndex + 1];
      const name = (pathParts[dpIndex - 1] || 'Amazon Product')
                   .replace(/-/g, ' ').slice(0, 50) + '...';
      return {
        name: `(Amazon) ${name}`,
        productId: asin,
        storeType: 'amazon',
        partNumber: null
      };
    }
    
    // --- CROMA LOGIC ---
    if (parsedUrl.hostname.includes('croma.com')) {
      const pathParts = parsedUrl.pathname.split('/');
      const pid = pathParts[pathParts.length - 1];
      if (!pid || !/^\d+$/.test(pid)) throw new Error('Could not find a valid product ID in the Croma URL.');
      const name = (pathParts[1] || 'Croma Product')
                   .replace(/-/g, ' ').slice(0, 50) + '...';
      return { 
        name: `(Croma) ${name}`, 
        productId: pid, 
        storeType: 'croma', 
        partNumber: null 
      };
    }

    throw new Error('Sorry, only Croma, Amazon, and Flipkart URLs are supported.');
  
  } catch (error) {
    return { error: error.message };
  }
}