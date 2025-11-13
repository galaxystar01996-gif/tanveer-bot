'use client';

import { useRef, useState } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

/**
 * Derives the storeType and checks if productId (Part Number) should be shown
 * based on the product URL.
 * @param {string} url 
 * @returns {object} { storeType, showPartNumber }
 */
function getStoreDetails(url) {
  const lowerUrl = url.toLowerCase();
  
  if (lowerUrl.includes('apple.com')) {
    return { storeType: 'unicorn', showPartNumber: true };
  }
  if (lowerUrl.includes('reliancedigital.in')) {
    return { storeType: 'reliance_digital', showPartNumber: false }; // URL is sufficient for RD
  }
  if (lowerUrl.includes('iqoo.com')) {
    return { storeType: 'iqoo', showPartNumber: false }; // URL is sufficient for iQOO
  }
  if (lowerUrl.includes('vivo.com')) {
    return { storeType: 'vivo', showPartNumber: false }; // URL is sufficient for Vivo
  }
  // For Croma or Flipkart, we generally need the explicit ID for API lookups.
  if (lowerUrl.includes('croma.com') || lowerUrl.includes('flipkart.com') || lowerUrl.includes('amazon.in')) {
     // Show the part number/product ID field for manual entry
    return { storeType: 'unknown', showPartNumber: true }; 
  }

  // Default fallback or general case
  return { storeType: 'unknown', showPartNumber: false };
}


export function AddProductForm({ addProductAction }) {
  const formRef = useRef(null);
  const [url, setUrl] = useState('');
  
  // Use the new derived details
  const { storeType, showPartNumber } = getStoreDetails(url);

  async function formAction(formData) {
    // Manually append the determined storeType before submitting
    formData.append('storeType', storeType);

    const result = await addProductAction(formData);
    
    if (result?.error) {
      toast.error(result.error);
    } else {
      toast.success("Product added to tracker!");
      formRef.current?.reset();
      setUrl(''); // Clear URL state after successful submission
    }
  }

  // Determine placeholder based on recognized store
  const placeholderText = storeType === 'unknown' 
    ? "Paste Product URL (e.g., Flipkart, Amazon, Reliance Digital, Vivo, iQOO)"
    : `Paste ${storeType.replace('_', ' ').toUpperCase()} URL`;


  return (
    <form ref={formRef} action={formAction} className="flex flex-col w-full space-y-3">
      <div className="flex w-full items-center space-x-2">
        <Input
          type="text"
          name="url"
          placeholder={placeholderText}
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <Button type="submit">Add Product</Button>
      </div>
      
      {/* This field is used for: 
        1. Apple Store/Unicorn: The actual Apple Part Number.
        2. Flipkart/Croma: The product ID required for their APIs (since the URL isn't enough).
        It is hidden if the store uses the URL for its main lookup chain (like Reliance Digital, Vivo, iQOO).
      */}
      {showPartNumber && (
        <Input
          type="text"
          name="productId" // Mapping to productId in actions.js/Prisma
          placeholder={storeType === 'unicorn' ? "Apple Part Number (e.g., MG6P4HN/A)" : "Product ID (Required for this store)"}
          required={storeType !== 'unicorn'} // Make it required only for general ID-based lookups like Croma/Flipkart
          className="transition-all duration-300"
        />
      )}

      {/* Hidden input to pass the derived storeType */}
      <input type="hidden" name="storeType" value={storeType} />

      {/* Affiliate Link */}
      <Input
        type="text"
        name="affiliateLink"
        placeholder="Your Affiliate Link (Optional)"
      />
    </form>
  );
}