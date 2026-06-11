#!/usr/bin/env python3
"""
Sample script: LLM Context Routing with BM25S Retrieval

This script demonstrates a primary use case for BM25S retrieval in LLM systems:
using lexical retrieval to filter a large context registry before calling the LLM.

The registry can contain tools, documents, chunked content, workflow actions, or other
structured context objects. In this example, the registry contains tools.

Flow:
1. User provides a query
2. BM25S retrieves top matching context items from a larger registry
3. Only the relevant items are passed to the LLM
4. The LLM selects the appropriate tool, document, or context item for the task

This pattern addresses:
- Context window limitations
- Tool/document confusion across similar entries
- Token usage optimization
- Permission and guardrail enforcement
- Hybrid RAG pipelines where lexical retrieval complements semantic retrieval
"""

import sys
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from axiolex import BM25SRetriever


class LLMContextRouter:
    """Context routing system that uses BM25S to filter tools/documents for LLM context."""
    
    def __init__(self, tool_registry_file: str = "source_files/tools_list.yaml"):
        """Initialize router with tool registry."""
        self.retriever = BM25SRetriever(document_file=tool_registry_file)
        self.max_items_for_llm = 5  # Limit context items to prevent prompt overflow
        
    def route_query(self, user_query: str, max_items: int = None) -> Dict[str, Any]:
        """
        Route user query to relevant context items.
        
        Args:
            user_query: Natural language query from user
            max_items: Maximum number of context items to return (default: 5)
            
        Returns:
            Dictionary with filtered context items and routing metadata
        """
        max_items = max_items or self.max_items_for_llm
        
        print(f"🔍 Routing query: '{user_query}'")
        print(f"📚 Total context items in registry: {len(self.retriever.documents)}")
        
        # Retrieve relevant context items using BM25S
        results = self.retriever.retrieve_documents(
            user_query, 
            temperature=0.5,  # Lower temp for more precise matching
            ignore_zero=True   # Filter out zero-relevance results
        )
        
        # Filter and format context items for LLM
        filtered_items = []
        for doc in results['documents'][:max_items]:
            metadata = doc.get('metadata', {})
            item_info = {
                "id": doc['id'],
                "title": doc['title'],
                "description": doc['content'],
                "keywords": doc.get('keywords', []),
                "metadata": metadata,
                "parameters": metadata.get('parameters', {}),
                "category": metadata.get('category', 'general'),
                "item_type": metadata.get('item_type', 'tool'),
                "relevance_score": doc['bm25_score']
            }
            filtered_items.append(item_info)
        
        routing_result = {
            "user_query": user_query,
            "total_items_found": len(results['documents']),
            "items_filtered": len(filtered_items),
            "max_items_limit": max_items,
            # Backward-compatible alias for this tool-focused example.
            "tools": filtered_items,
            "items": filtered_items,
            "routing_metadata": {
                "cutoff_percentage": results.get('cutoff_percentage', 0),
                "settings_used": results.get('settings', {})
            }
        }
        
        print(f"✅ Found {len(results['documents'])} relevant context items")
        print(f"🎯 Filtered to {len(filtered_items)} items for LLM")
        
        return routing_result
    
    def format_context_for_llm(self, routing_result: Dict[str, Any]) -> str:
        """
        Format filtered context items for LLM context.
        
        Args:
            routing_result: Result from route_query()
            
        Returns:
            Formatted string for LLM prompt
        """
        items = routing_result['items']
        
        if not items:
            return "No relevant context items found for this query."
        
        prompt_parts = [
            f"Available context for query: '{routing_result['user_query']}'",
            f"Found {routing_result['total_items_found']} matching items, showing top {len(items)}:",
            ""
        ]
        
        for i, item in enumerate(items, 1):
            prompt_parts.extend([
                f"{i}. {item['title']} (ID: {item['id']}, Type: {item['item_type']})",
                f"   Description: {item['description']}",
                f"   Relevance: {item['relevance_score']:.2f}",
            ])
            
            if item['parameters']:
                params = item['parameters']
                if isinstance(params, dict):
                    param_list = [f"- {k}: {v.get('type', 'unknown')}" for k, v in params.items()]
                    prompt_parts.append(f"   Parameters: {', '.join(param_list)}")
            
            prompt_parts.append("")
        
        prompt_parts.extend([
            "Please use only the relevant context items listed above for the user's request.",
            "If the selected item is a tool, choose the most appropriate tool and required arguments."
        ])
        
        return "\n".join(prompt_parts)
    
    def simulate_llm_response(self, routing_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate LLM tool selection (in real usage, this would call an actual LLM).
        
        Args:
            routing_result: Result from route_query()
            
        Returns:
            Simulated LLM response
        """
        items = routing_result['items']
        user_query = routing_result['user_query']
        
        # Simple simulation: pick the highest scoring item
        if items:
            selected_item = max(items, key=lambda x: x['relevance_score'])
            
            return {
                "selected_item": selected_item['id'],
                "selected_type": selected_item['item_type'],
                "confidence": selected_item['relevance_score'],
                "reasoning": f"Selected '{selected_item['title']}' as it best matches '{user_query}' with relevance score {selected_item['relevance_score']:.2f}",
                "next_action": f"Would use context item: {selected_item['id']}"
            }
        else:
            return {
                "selected_item": None,
                "selected_type": None,
                "confidence": 0.0,
                "reasoning": f"No relevant context found for query: '{user_query}'",
                "next_action": "Ask user for clarification"
            }


def demonstrate_tool_routing():
    """Demonstrate the tool routing workflow."""
    print("=" * 60)
    print("LLM Context Routing Demonstration")
    print("=" * 60)
    
    # Initialize router
    router = LLMContextRouter()
    
    # Test queries representing different user intents
    test_queries = [
        "I need to look up a customer's profile information",
        "Can you help me track my order?",
        "I want to process a refund for my purchase",
        "Check if a product is in stock",
        "Create a new support ticket for technical issues",
        "Schedule a follow-up call with a customer"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*20} Test Case {i} {'='*20}")
        
        # Step 1: Route query to relevant tools
        routing_result = router.route_query(query, max_items=3)
        
        # Step 2: Format tools for LLM
        llm_context = router.format_context_for_llm(routing_result)
        print(f"\n📝 LLM Context Preview:")
        print("-" * 40)
        print(llm_context[:500] + "..." if len(llm_context) > 500 else llm_context)
        print("-" * 40)
        
        # Step 3: Simulate LLM decision
        llm_response = router.simulate_llm_response(routing_result)
        print(f"\n🤖 Simulated LLM Response:")
        print(f"Selected: {llm_response['selected_item']} ({llm_response['selected_type']})")
        print(f"Confidence: {llm_response['confidence']:.2f}")
        print(f"Reasoning: {llm_response['reasoning']}")


def compare_routing_strategies():
    """Compare different routing configurations."""
    print(f"\n{'='*20} Routing Strategy Comparison {'='*20}")
    
    router = LLMContextRouter()
    query = "customer order management and billing"
    
    strategies = [
        {"name": "Precise (temp=0.3, max=3)", "temp": 0.3, "max": 3},
        {"name": "Balanced (temp=0.7, max=5)", "temp": 0.7, "max": 5},
        {"name": "Broad (temp=1.2, max=7)", "temp": 1.2, "max": 7}
    ]
    
    for strategy in strategies:
        print(f"\n🔧 Strategy: {strategy['name']}")
        
        results = router.retriever.retrieve_documents(
            query,
            temperature=strategy['temp'],
            ignore_zero=True
        )
        
        filtered = results['documents'][:strategy['max']]
        
        print(f"   Found: {len(results['documents'])} items")
        print(f"   Filtered to: {len(filtered)} items")
        
        for doc in filtered:
            print(f"   - {doc['title']} (Score: {doc['bm25_score']:.2f})")


def context_window_analysis():
    """Analyze token usage and context window implications."""
    print(f"\n{'='*20} Context Window Analysis {'='*20}")
    
    router = LLMContextRouter()
    
    # Simulate different registry sizes
    registry_sizes = [10, 50, 100, 500]  # Simulated context item counts
    
    query = "customer profile and order history"
    
    print("Analyzing context reduction for different registry sizes:")
    print("-" * 60)
    
    for size in registry_sizes:
        # Simulate routing (in real usage, this would use actual registry size)
        routing_result = router.route_query(query, max_items=5)
        
        # Estimate tokens (rough approximation: ~4 chars per token)
        tools_context = router.format_context_for_llm(routing_result)
        estimated_tokens = len(tools_context) // 4
        
        # Calculate reduction
        full_registry_tokens = size * 200  # Rough estimate: 200 tokens per context item
        reduction_percentage = ((full_registry_tokens - estimated_tokens) / full_registry_tokens) * 100
        
        print(f"Registry: {size:3d} items → Context: {estimated_tokens:4d} tokens "
              f"(reduced by {reduction_percentage:5.1f}%)")


def advanced_routing_example():
    """Advanced routing with permission filtering and categories."""
    print(f"\n{'='*20} Advanced Routing Example {'='*20}")
    
    router = LLMContextRouter()
    
    # Simulate permission-based routing
    class PermissionRouter(LLMContextRouter):
        def route_query_with_permissions(self, user_query: str, user_permissions: List[str]) -> Dict[str, Any]:
            """Route with permission filtering."""
            base_result = self.route_query(user_query)
            
            # Filter items by user permissions
            original_item_count = len(base_result['items'])
            permitted_items = []
            for item in base_result['items']:
                item_category = item.get('category', 'general')
                if item_category in user_permissions or 'admin' in user_permissions:
                    permitted_items.append(item)
            
            base_result['items'] = permitted_items
            base_result['items_filtered'] = len(permitted_items)
            base_result['items_filtered_out'] = original_item_count - len(permitted_items)
            # Backward-compatible alias for this tool-focused example.
            base_result['tools'] = permitted_items
            base_result['permission_filter'] = {
                'user_permissions': user_permissions,
                'items_filtered_out': original_item_count - len(permitted_items)
            }
            
            return base_result
    
    perm_router = PermissionRouter()
    
    # Test with different permission levels
    test_cases = [
        {"query": "customer profile lookup", "permissions": ["crm", "orders"]},
        {"query": "system configuration", "permissions": ["crm"]},  # No admin access
        {"query": "refund processing", "permissions": ["admin"]}  # Full access
    ]
    
    for case in test_cases:
        print(f"\n🔐 Query: '{case['query']}'")
        print(f"👤 Permissions: {case['permissions']}")
        
        result = perm_router.route_query_with_permissions(case['query'], case['permissions'])
        
        print(f"✅ Items available: {len(result['items'])}")
        if result['permission_filter']['items_filtered_out'] > 0:
            print(f"🚫 Items filtered by permissions: {result['permission_filter']['items_filtered_out']}")
        
        for item in result['items']:
            print(f"   - {item['title']}")


if __name__ == "__main__":
    print("BM25S LLM Context Routing Examples")
    print("This demonstrates lexical context filtering for LLM tools, documents, and chunks")
    print("=" * 80)
    
    try:
        # Run all demonstrations
        demonstrate_tool_routing()
        compare_routing_strategies()
        context_window_analysis()
        advanced_routing_example()
        
        print("\n" + "=" * 80)
        print("✅ All LLM context routing examples completed!")
        print("\nKey Benefits Demonstrated:")
        print("• Reduced context window (from hundreds of items to 5-10 relevant items)")
        print("• Improved relevance through BM25S + PyStemmer lexical matching")
        print("• Permission-based filtering for security and guardrails")
        print("• Configurable routing strategies for narrow or broad recall")
        print("• Token usage and prompt-cost optimization")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure the source_files/tools_list.yaml file exists")
        print("You can adapt this example to route tools, documents, chunks, or other context objects.")
        sys.exit(1)
