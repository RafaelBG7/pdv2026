using System.Text.Json;
using Girofy.Application.Models;

namespace Girofy.UnitTests;

public sealed class StockModelsTests
{
    [Fact]
    public void Movement_contract_maps_type_origin_balances_and_historical_costs()
    {
        const string json = """
        {
          "id": 31,
          "movement_type": "sale",
          "movement_type_label": "Saída",
          "source_type": "kit_sale",
          "source_type_label": "Venda de kit",
          "origin": "kit_sale",
          "origin_label": "Venda de kit",
          "source_id": 18,
          "reference": "Venda #18",
          "quantity": 2,
          "signed_quantity": -2,
          "previous_stock": 10,
          "new_stock": 8,
          "unit_cost": 4.25,
          "total_cost": 8.50,
          "balance_consistent": true,
          "reason": "Venda do kit Festa",
          "notes": "",
          "product": { "id": 9, "name": "Refrigerante", "category": { "id": 2, "name": "Bebidas" } },
          "user": { "id": 4, "username": "operador" }
        }
        """;

        var movement = JsonSerializer.Deserialize<StockMovementRecord>(json)!;

        Assert.Equal("Saída", movement.TypeLabel);
        Assert.Equal("Venda de kit", movement.OriginText);
        Assert.Equal("-2 un.", movement.QuantityText);
        Assert.Equal("10 un.", movement.PreviousStockText);
        Assert.Equal("8 un.", movement.NewStockText);
        Assert.Equal("Venda #18", movement.ReferenceText);
        Assert.Equal("Saldo conferido", movement.BalanceStatusText);
        Assert.NotEqual("Restrito", movement.UnitCostText);
        Assert.NotEqual("Restrito", movement.TotalCostText);
    }

    [Fact]
    public void Legacy_or_restricted_movement_uses_safe_fallbacks_without_inventing_data()
    {
        const string json = """
        {
          "id": 7,
          "movement_type": "legacy",
          "movement_type_label": "",
          "source_type": "",
          "source_type_label": "",
          "origin": "",
          "origin_label": "",
          "quantity": 3,
          "signed_quantity": 0,
          "previous_stock": 4,
          "new_stock": 7,
          "unit_cost": null,
          "total_cost": null,
          "balance_consistent": false,
          "reason": "",
          "notes": ""
        }
        """;

        var movement = JsonSerializer.Deserialize<StockMovementRecord>(json)!;

        Assert.Equal("Não informado", movement.TypeLabel);
        Assert.Equal("Não informado", movement.OriginText);
        Assert.Equal("+3 un.", movement.QuantityText);
        Assert.Equal("Produto removido", movement.ProductName);
        Assert.Equal("Sistema", movement.UserName);
        Assert.Equal("Não informado", movement.ReasonText);
        Assert.Equal("Sem referência", movement.ReferenceText);
        Assert.Equal("Restrito", movement.UnitCostText);
        Assert.Equal("Restrito", movement.TotalCostText);
        Assert.Equal("Saldo inconsistente", movement.BalanceStatusText);
    }
}
