package rag

default allow = true

allow = false {
    input.query
    contains(lower(input.query), "绕过权限")
}

allow = false {
    some role
    role := input.user_context.roles[_]
    role == "guest"
    contains(lower(input.query), "机密")
}
