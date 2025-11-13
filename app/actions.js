'use server';

import { prisma } from '@/lib/prisma';
import { revalidatePath } from 'next/cache';

// This function parses the URL you paste in
function getProductDetails(url, partNumber) {
    try {
        const parsedUrl = new URL(url);

        // --- NEW VIVO LOGIC ---
        if (parsedUrl.hostname.includes('vivo.com') && !parsedUrl.hostname.includes('iqoo.com')) {
            // Vivo product ID is typically the last segment of the path after the product name
            const pathParts = parsedUrl.pathname.split('/').filter(p => p.length > 0);
            const pid = pathParts[pathParts.length - 1];

            if (!pid || pid.length < 5) throw new Error('Could not find a valid product ID in the Vivo URL.');

            const name = (pathParts[pathParts.length - 2] || 'Vivo Product')
                .replace(/-/g, ' ').slice(0, 50) + '...';

            return {
                name: `(Vivo) ${name}`,
                productId: pid,
                storeType: 'vivo',
                partNumber: null
            };
        }

        // --- NEW IQOO LOGIC ---
        if (parsedUrl.hostname.includes('iqoo.com')) {
            // iQOO product ID is typically the last segment of the path after the product name
            const pathParts = parsedUrl.pathname.split('/').filter(p => p.length > 0);
            const pid = pathParts[pathParts.length - 1];

            if (!pid || pid.length < 5) throw new Error('Could not find a valid product ID in the iQOO URL.');

            const name = (pathParts[pathParts.length - 2] || 'iQOO Product')
                .replace(/-/g, ' ').slice(0, 50) + '...';

            return {
                name: `(iQOO) ${name}`,
                productId: pid,
                storeType: 'iqoo',
                partNumber: null
            };
        }

        // --- NEW RELIANCE DIGITAL LOGIC ---
        if (parsedUrl.hostname.includes('reliancedigital.in')) {
            // Example path: /product/apple-iphone-17-256-gb-black-mff8ru-9391619
            const pathParts = parsedUrl.pathname.split('/').filter(p => p.length > 0);
            // The last segment contains the name/slug and the short ID
            const slug = pathParts[pathParts.length - 1]; 
            
            if (!slug || slug.length < 5) throw new Error('Could not find a valid product slug in the Reliance Digital URL.');
            
            // For display name, try to use the preceding segment, or clean the slug itself
            const nameBase = pathParts.length > 1 ? pathParts[pathParts.length - 2] : slug;
            const name = nameBase.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase()).slice(0, 50) + '...';

            return { 
                name: `(R. Digital) ${name}`, 
                // We use the full slug. The Python checker will extract the item_code using this slug.
                productId: slug, 
                storeType: 'reliance_digital', 
                partNumber: null 
            };
        }

        // --- NEW FLIPKART LOGIC ---
        if (parsedUrl.hostname.includes('flipkart.com')) {
            // Flipkart ID is in the 'pid' query parameter
            const pid = parsedUrl.searchParams.get('pid');
            if (!pid) {
                throw new Error('Flipkart URL is missing a "pid" query parameter.');
            }
            // Get a name from the URL path
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
            // Find the ASIN, which is usually after /dp/
            const pathParts = parsedUrl.pathname.split('/');
            const dpIndex = pathParts.indexOf('dp');

            if (dpIndex === -1 || !pathParts[dpIndex + 1]) {
                throw new Error('Could not find a valid ASIN (e.g., /dp/B0CX59H5W7) in the Amazon URL.');
            }

            const asin = pathParts[dpIndex + 1];
            const name = (pathParts[dpIndex - 1] || 'Amazon Product')
                .replace(/-/g, ' ').slice(0, 50) + '...';

            return {
                name: `(Amazon) ${name}`,
                productId: asin, // For Amazon, the ASIN is the Product ID
                storeType: 'amazon',
                partNumber: null // We don't need this for Amazon
            };
        }

        // --- APPLE LOGIC ---
        if (parsedUrl.hostname.includes('apple.com')) {
            if (!partNumber) {
                throw new Error('Apple products require a Part Number.');
            }
            const name = (parsedUrl.pathname.split('/')[3] || 'Apple Product')
                .replace(/-/g, ' ').slice(0, 50) + '...';
            return {
                name: `(Apple) ${name}`,
                productId: partNumber,
                storeType: 'apple',
                partNumber: partNumber
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

        // --- UPDATED ERROR MESSAGE ---
        throw new Error('Sorry, only Croma, Apple, Amazon, Flipkart, Vivo, iQOO, and Reliance Digital URLs are supported.');

    } catch (error) {
        return { error: error.message };
    }
}

// Server Action to add a product (no changes needed)
export async function addProduct(formData) {
    const url = formData.get('url');
    const partNumber = formData.get('partNumber');
    const affiliateLink = formData.get('affiliateLink');

    if (!url) return { error: 'URL is required.' };

    const details = getProductDetails(url, partNumber);
    if (details.error) return { error: details.error };

    try {
        await prisma.product.create({
            data: {
                name: details.name,
                url: url,
                productId: details.productId,
                storeType: details.storeType,
                partNumber: details.partNumber,
                affiliateLink: affiliateLink || null,
            },
        });
        revalidatePath('/');
        return { success: `Added ${details.name}` };
    } catch (error) {
        console.error(error);
        return { error: 'Failed to add product. Is it a duplicate?' };
    }
}

// deleteProduct (no changes needed)
export async function deleteProduct(id) {
    if (!id) return;
    try {
        await prisma.product.delete({ where: { id: id } });
        revalidatePath('/');
    } catch (error) {}
}