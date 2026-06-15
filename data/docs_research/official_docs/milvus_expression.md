---
id: expression.md
title: Predicate Expressions
---

# Predicate Expressions
A predicate is an expression evaluated to a Boolean value. Milvus conducts scalar filtering by searching with predicates. A predicate expression, when evaluated, returns either TRUE or FALSE.

View Python SDK API Reference for information about how to use predicate expressions.

# Predicate Grammers
Expression can be either NONE or a logic expression.
```haskell
Expr := LogicalExpr | NIL
```

## Types of predicate operators


 operator type
 Description
 Examples


 Relational Expression
 Relational operators use symbols to check for equality, inequality, or relative order between two expressions. Relational operators include: >, >=,


- A > 1

- B >= 2

- C

- D

- E == 5

- F != 6


 Logical operators
 An operator that performs a comparison between two expression. The supported logical operators are: AND, && OR, ||, and NOT.


- A > 3 && A

- NOT (A == 1)


 IN Expression
 The IN condition is satisfied when the expression to the left of the keyword IN is included in the list of items.


- FloatCol in [1.0, 2, 3.0]

- Int64Col in [1, 2, 3]


# Relational operators
The relational operators are symbols that compare one expression with another expression. Data type between left and right side of the operator must match.

The supported operators are:


- equals(==)

- not equals(!=)

- is greater than (>)

- is greater than or equal to (>=)

- is less than (

# IN Operator
The IN operator matches the values in a field to any of the items in the constant array. The items in the constant array must be a comma-separated list. Data type between left and right side of the operator must match.

## Syntax
```haskell
InExpr := IDENTIFIER "in" ConstantArray
ConstantArray := "[" Constant+, "]"
```

# Logical operators
There are two types of logical operators, unary and binray. UnaryLogicalOp act on another logical expression, while BinaryLogicalOp compare one logic expression with another logic expression.

The supported operators are:


- NOT !

- AND &&

- OR ||


## Syntax
```haskell
LogicalExpr := LogicalExpr BinaryLogicalOp LogicalExpr
 | UnaryLogicalOp LogicalExpr
 | "(" LogicalExpr ")"
 | RelationalExpr
 | InExpr
```

## Order of evaluation
The order in which the Milvus evaluates predicate expressions follows the table below:

1. Expressions inside parentheses
2. Not operators
3. Or operators
4. And Operators