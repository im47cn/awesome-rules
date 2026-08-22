package com.acme.demo.infra.mapper;

import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface OrderMapper {
    int insert(Object agg);
}
