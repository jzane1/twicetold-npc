Shader "Twicetold/Valley Sky"
{
    Properties { _SunDirection("Sun direction",Vector)=(.3,.7,.2,0) }
    SubShader
    {
        Tags {"Queue"="Background" "RenderType"="Background" "PreviewType"="Skybox"}
        Cull Off ZWrite Off
        Pass
        {
            HLSLPROGRAM
            #pragma vertex Vert
            #pragma fragment Frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            float4 _SunDirection;
            struct A {float4 p:POSITION;};struct V {float4 p:SV_POSITION;float3 ray:TEXCOORD0;};
            float hash(float2 p){return frac(sin(dot(p,float2(127.1,311.7)))*43758.5453);}
            float n(float2 p){float2 i=floor(p),f=frac(p);f=f*f*(3-2*f);return lerp(lerp(hash(i),hash(i+float2(1,0)),f.x),lerp(hash(i+float2(0,1)),hash(i+1),f.x),f.y);}
            float fbm(float2 p){return n(p)*.57+n(p*2.03+13)*.27+n(p*4.07+7)*.11+n(p*8.1)*.05;}
            V Vert(A i){V o;o.p=TransformObjectToHClip(i.p.xyz);o.ray=i.p.xyz;return o;}
            half4 Frag(V i):SV_Target
            {
                float3 d=normalize(i.ray);
                float3 sky=lerp(float3(.60,.75,.81),float3(.19,.40,.67),pow(saturate(d.y),.48));
                float2 p=d.xz/max(.13,d.y+.09)*1.45+float2(_Time.y*.0008,0);
                float cloud=smoothstep(.55,.70,fbm(p))*smoothstep(.03,.15,d.y)*(1-smoothstep(.77,.98,d.y));
                float3 white=lerp(float3(.70,.77,.79),float3(.95,.94,.87),smoothstep(.54,.70,fbm(p+float2(.08,.13))));
                sky=lerp(sky,white,cloud*.92);
                float sun=dot(d,normalize(_SunDirection.xyz));sky+=float3(1,.85,.57)*smoothstep(.9994,.99985,sun)*.55;
                return half4(sky,1);
            }
            ENDHLSL
        }
    }
}
