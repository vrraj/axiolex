#!/bin/bash
# BM25S Retriever - REST API Examples using curl
# This script demonstrates how to use the BM25S API via curl commands
# Make sure server is running: axiolex-server --config settings.yaml

BASE_URL="http://localhost:9200"

echo "=========================================="
echo "BM25S Retriever - curl API Examples"
echo "=========================================="
echo "Base URL: $BASE_URL"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print section header
print_section() {
    echo ""
    echo "=========================================="
    echo "$1"
    echo "=========================================="
}

# Function to check server connection
check_server() {
    print_section "1. Check Server Connection"
    echo "GET /settings"
    response=$(curl -s -w "\n%{http_code}" "$BASE_URL/settings")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -eq 200 ]; then
        echo -e "${GREEN}✅ Server is running${NC}"
        echo "Response:"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
    else
        echo -e "${RED}❌ Server not accessible (HTTP $http_code)${NC}"
        echo "Make sure server is running: axiolex-server --config settings.yaml"
        exit 1
    fi
}

# Function to search documents
search_documents() {
    print_section "2. Search Documents"
    
    query="curl api test"
    echo "POST /retrieve"
    echo "Query: $query"
    
    search_data="{\"query\": \"$query\"}"
    
    response=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/retrieve" \
        -H "Content-Type: application/json" \
        -d "$search_data")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -eq 200 ]; then
        echo -e "${GREEN}✅ Search completed${NC}"
        echo "Response:"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
    else
        echo -e "${RED}❌ Search failed (HTTP $http_code)${NC}"
        echo "Response: $body"
    fi
}

# Function to get all documents
get_all_documents() {
    print_section "3. Get All Documents"
    echo "GET /documents"
    
    response=$(curl -s -w "\n%{http_code}" "$BASE_URL/documents")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -eq 200 ]; then
        echo -e "${GREEN}✅ Retrieved documents${NC}"
        echo "Response:"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
    else
        echo -e "${RED}❌ Failed to get documents (HTTP $http_code)${NC}"
        echo "Response: $body"
    fi
}

# Function to search with parameters
search_with_params() {
    print_section "4. Search with Parameters"
    
    query="api"
    echo "POST /retrieve with custom parameters"
    echo "Query: $query"
    echo "Temperature: 0.5, Ignore Zero: true, Cutoff: 10.0"
    
    search_data='{
        "query": "api",
        "temperature": 0.5,
        "ignore_zero": true,
        "llm_tools_cutoff": 10.0
    }'
    
    response=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/retrieve" \
        -H "Content-Type: application/json" \
        -d "$search_data")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -eq 200 ]; then
        echo -e "${GREEN}✅ Search with params completed${NC}"
        echo "Response:"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
    else
        echo -e "${RED}❌ Search with params failed (HTTP $http_code)${NC}"
        echo "Response: $body"
    fi
}

# Function to get settings
get_settings() {
    print_section "5. Get Current Settings"
    echo "GET /settings"
    
    response=$(curl -s -w "\n%{http_code}" "$BASE_URL/settings")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -eq 200 ]; then
        echo -e "${GREEN}✅ Settings retrieved${NC}"
        echo "Response:"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
    else
        echo -e "${RED}❌ Failed to get settings (HTTP $http_code)${NC}"
        echo "Response: $body"
    fi
}

# Function to update settings
update_settings() {
    print_section "6. Update Settings"
    
    new_settings='{
        "temperature": 0.8,
        "ignore_zero": true,
        "llm_tools_cutoff": 12.0
    }'
    
    echo "POST /settings"
    echo "Payload:"
    echo "$new_settings" | jq '.' 2>/dev/null || echo "$new_settings"
    
    response=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/settings" \
        -H "Content-Type: application/json" \
        -d "$new_settings")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -eq 200 ]; then
        echo -e "${GREEN}✅ Settings updated successfully${NC}"
        echo "Response:"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
    else
        echo -e "${RED}❌ Failed to update settings (HTTP $http_code)${NC}"
        echo "Response: $body"
    fi
}

# Main execution
main() {
    check_server
    search_documents
    get_all_documents
    search_with_params
    get_settings
    update_settings
    
    print_section "All curl examples completed!"
    echo -e "${GREEN}✅ Done${NC}"
}

# Run main function
main
