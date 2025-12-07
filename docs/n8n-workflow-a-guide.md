# n8n Workflow A: Loan Product Discovery (Web Crawler)

## Workflow Overview
This workflow automatically discovers personal loan products from financial websites on a daily schedule.

## Trigger
- **Node Type**: Schedule Trigger
- **Cron Expression**: `0 2 * * *` (Daily at 2 AM)
- **Name**: "Daily Loan Crawler"

## Workflow Steps

### 1. Schedule Trigger Node
```
Name: Daily Loan Crawler
Trigger Times: Cron
Cron Expression: 0 2 * * *
```

### 2. Define Target Websites
**Node Type**: Set (or Code)
**Name**: "Target Websites"
**Purpose**: Define list of websites to crawl

```javascript
// Example websites (choose 2-3 real ones)
return [
  {
    json: {
      name: "BankA Personal Loans",
      url: "https://www.example-bank-a.com/personal-loans",
      provider: "Bank A"
    }
  },
  {
    json: {
      name: "BankB Personal Loans",
      url: "https://www.example-bank-b.com/loans/personal",
      provider: "Bank B"
    }
  },
  {
    json: {
      name: "LenderC Personal Loans",
      url: "https://www.example-lender-c.com/products/personal-loans",
      provider: "Lender C"
    }
  }
];
```

### 3. HTTP Request Node (for each website)
**Node Type**: HTTP Request
**Name**: "Fetch Webpage"
**Settings**:
- Method: GET
- URL: `{{ $json.url }}`
- Response Format: String (HTML)
- Options:
  - Timeout: 30000
  - Follow Redirect: true

### 4. HTML Extract Node
**Node Type**: HTML Extract
**Name**: "Extract Loan Data"
**Purpose**: Parse HTML and extract loan product information

**Extraction Rules** (adjust selectors based on actual websites):
```
Extraction Values:
- product_name: CSS Selector → .loan-name, h2.product-title
- interest_rate: CSS Selector → .interest-rate, .apr
- min_income: CSS Selector → .min-income, .eligibility-income
- min_credit_score: CSS Selector → .min-credit, .credit-requirement
```

**Note**: Each website will have different HTML structure. You'll need to inspect the actual websites and adjust selectors.

### 5. Code Node: Parse and Clean Data
**Node Type**: Code (JavaScript)
**Name**: "Clean and Structure Data"

```javascript
const items = $input.all();
const cleanedData = [];

for (const item of items) {
  try {
    // Extract and clean interest rate
    const rateText = item.json.interest_rate || '';
    const rate = parseFloat(rateText.replace(/[^\d.]/g, ''));

    // Extract and clean income requirement
    const incomeText = item.json.min_income || '';
    const minIncome = parseFloat(incomeText.replace(/[^\d.]/g, ''));

    // Extract and clean credit score
    const creditText = item.json.min_credit_score || '';
    const minCredit = parseInt(creditText.replace(/[^\d]/g, ''));

    cleanedData.push({
      json: {
        product_name: item.json.product_name || 'Unknown Product',
        provider: $('Set').item.json.provider,
        source_url: $('Set').item.json.url,
        interest_rate: isNaN(rate) ? null : rate,
        min_income: isNaN(minIncome) ? null : minIncome,
        min_credit_score: isNaN(minCredit) ? null : minCredit,
        max_credit_score: 850,  // Default max
        min_age: 18,
        max_age: 75,
        loan_amount_min: 1000,  // Default values
        loan_amount_max: 50000,
        eligibility_criteria: {
          employment_required: 'employed',
          source_last_checked: new Date().toISOString()
        }
      }
    });
  } catch (error) {
    console.error('Error processing item:', error);
  }
}

return cleanedData;
```

### Alternative: Use AI to Extract Data (More Robust)

**Node Type**: OpenAI / Google Gemini
**Name**: "AI Extract Loan Data"
**Purpose**: Use LLM to extract structured data from HTML

```
Prompt Template:
Extract personal loan product information from the following HTML content.
Return ONLY a JSON object with these fields:
- product_name: string
- interest_rate: number (percentage)
- min_income: number (monthly income requirement)
- min_credit_score: number
- loan_amount_range: string

HTML Content:
{{ $json.html_content }}

Return ONLY valid JSON, no additional text.
```

**Settings**:
- Model: gpt-3.5-turbo or gemini-pro
- Max Tokens: 500
- Temperature: 0.1

### 6. PostgreSQL Node
**Node Type**: PostgreSQL
**Name**: "Insert/Update Loan Products"
**Credential**: loan_eligibility_db

**Operation**: Insert or Update
**Table**: loan_products

**SQL Query** (use Execute Query mode):
```sql
INSERT INTO loan_products (
  product_name,
  provider,
  interest_rate,
  min_income,
  min_credit_score,
  max_credit_score,
  min_age,
  max_age,
  loan_amount_min,
  loan_amount_max,
  source_url,
  eligibility_criteria,
  updated_at
) VALUES (
  $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, CURRENT_TIMESTAMP
)
ON CONFLICT (product_name, provider)
DO UPDATE SET
  interest_rate = EXCLUDED.interest_rate,
  min_income = EXCLUDED.min_income,
  min_credit_score = EXCLUDED.min_credit_score,
  source_url = EXCLUDED.source_url,
  eligibility_criteria = EXCLUDED.eligibility_criteria,
  updated_at = CURRENT_TIMESTAMP;
```

**Parameters** (mapped from previous node):
- $1: {{ $json.product_name }}
- $2: {{ $json.provider }}
- $3: {{ $json.interest_rate }}
- $4: {{ $json.min_income }}
- $5: {{ $json.min_credit_score }}
- $6: {{ $json.max_credit_score }}
- $7: {{ $json.min_age }}
- $8: {{ $json.max_age }}
- $9: {{ $json.loan_amount_min }}
- $10: {{ $json.loan_amount_max }}
- $11: {{ $json.source_url }}
- $12: {{ JSON.stringify($json.eligibility_criteria) }}

### 7. Summary Node (Optional)
**Node Type**: Code
**Name**: "Crawl Summary"

```javascript
const items = $input.all();
return [{
  json: {
    total_products_found: items.length,
    timestamp: new Date().toISOString(),
    status: 'completed'
  }
}];
```

## Example Website Targets

Since we're in a learning/demo environment, you can use these approaches:

### Option 1: Mock Data (for testing)
Create a Set node with sample data instead of web scraping:

```javascript
return [
  {
    json: {
      product_name: "Quick Personal Loan",
      provider: "Bank A",
      interest_rate: 8.5,
      min_income: 3000,
      min_credit_score: 650,
      max_credit_score: 850,
      min_age: 21,
      max_age: 65,
      loan_amount_min: 5000,
      loan_amount_max: 50000,
      source_url: "https://example.com/loan1",
      eligibility_criteria: {
        employment_required: "employed"
      }
    }
  },
  {
    json: {
      product_name: "Premium Personal Loan",
      provider: "Bank A",
      interest_rate: 6.99,
      min_income: 5000,
      min_credit_score: 720,
      max_credit_score: 850,
      min_age: 25,
      max_age: 60,
      loan_amount_min: 10000,
      loan_amount_max: 100000,
      source_url: "https://example.com/loan2",
      eligibility_criteria: {
        employment_required: "employed"
      }
    }
  }
  // Add 8-10 more varied products
];
```

### Option 2: Real Financial Sites
Research and target these types of sites:
- SoFi personal loans page
- Marcus by Goldman Sachs
- LendingClub
- Upstart

**Important**: Check robots.txt and terms of service before scraping.

## Error Handling

Add an **Error Trigger** node to handle failures:
- Log errors to a separate table
- Send notification if crawl fails
- Retry logic for failed websites

## Testing

1. Test with "Execute Workflow" button
2. Verify data is inserted into loan_products table:
   ```sql
   SELECT * FROM loan_products ORDER BY created_at DESC LIMIT 10;
   ```
3. Check for duplicate prevention
4. Validate data quality

## Activation

Once tested, activate the workflow to run on schedule.
